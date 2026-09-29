import streamlit as st
import pandas as pd
from datetime import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# スマホ向けに最適化された設定
st.set_page_config(page_title="日次報告フォーム", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .title {text-align: center; font-size: 1.5rem; font-weight: bold; color: #1e40af; margin-bottom: 20px;}
    .metric-box {background-color: #f0fdf4; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #22c55e; margin-top: 20px;}
    .big-number {font-size: 3rem; font-weight: bold; color: #16a34a; margin: 10px 0;}
    .sub-text {font-size: 1.1rem; color: #475569;}
    
    /* 入力エリアをスマホで押しやすくする */
    div[data-baseweb="input"] {font-size: 1.2rem !important;}
    .stButton>button {padding: 15px 0; font-size: 1.2rem; font-weight: bold; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📱 現場日次報告ツール</div>', unsafe_allow_html=True)

FACILITY_CONFIG = {
    "リハビリ教室新松戸": {"week": 84, "sat": 40},
    "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
    "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
    "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
}

@st.cache_data(ttl=60)
def get_reported_dates():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        if os.path.exists('credentials.json'):
            credentials = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        else:
            credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
        client = gspread.authorize(credentials)
        worksheet = client.open_by_key('1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4').get_worksheet_by_id(1338228675)
        df = pd.DataFrame(worksheet.get_all_records())
        return df[['事業所名', '営業日']]
    except Exception:
        return pd.DataFrame(columns=['事業所名', '営業日'])

facility = st.selectbox("🏢 事業所名", list(FACILITY_CONFIG.keys()))

# --- 未報告日付の自動計算 ---
df_dates = get_reported_dates()
if not df_dates.empty:
    reported_str = df_dates[df_dates['事業所名'] == facility]['営業日'].tolist()
    reported_dates = [pd.to_datetime(d).date() for d in reported_str if str(d).strip() != '']
else:
    reported_dates = []

today = datetime.today().date()
missing_dates = []

# 過去30日間をチェック（日曜休み）
for i in range(30):
    d = today - pd.Timedelta(days=i)
    if d.weekday() != 6:  # 日曜(6)以外
        if d not in reported_dates:
            missing_dates.append(d)

# UI: 日付の選択
options = missing_dates + ["📅 カレンダーから手動で選ぶ..."]

def format_date_option(x):
    if isinstance(x, str):
        return x
    elif x == today:
        return f"{x.strftime('%Y/%m/%d')} (今日)"
    else:
        return f"{x.strftime('%Y/%m/%d')} (未報告)"

selected_option = st.selectbox("📅 報告する日付", options, format_func=format_date_option)

if isinstance(selected_option, str):
    date = st.date_input("カレンダーから日付を選択", today)
else:
    date = selected_option

st.markdown("### 👥 本日の利用人数")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**【要介護】**")
    am_k = st.number_input("午前 (介護)", min_value=0, value=0)
    pm_k = st.number_input("午後 (介護)", min_value=0, value=0)
    day_k = st.number_input("1日 (介護)", min_value=0, value=0)
with col2:
    st.markdown("**【支援・総合】**")
    am_s = st.number_input("午前 (支援)", min_value=0, value=0)
    pm_s = st.number_input("午後 (支援)", min_value=0, value=0)
    day_s = st.number_input("1日 (支援)", min_value=0, value=0)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🚀 報告を送信する", use_container_width=True, type="primary"):
    with st.spinner("スプレッドシートに保存中..."):
        try:
            # 認証とスプレッドシートの取得（本番・ローカル両対応）
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            if os.path.exists('credentials.json'):
                credentials = Credentials.from_service_account_file('credentials.json', scopes=scopes)
            else:
                credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
                
            client = gspread.authorize(credentials)
            # URLのIDとGIDからシートを特定
            sheet_id = '1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4'
            worksheet = client.open_by_key(sheet_id).get_worksheet_by_id(1338228675)
            
            # スプレッドシートに書き込む行データを作成
            now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            date_str = date.strftime("%Y/%m/%d")
            
            row_data = [now_str, facility, date_str, am_k, am_s, pm_k, pm_s, day_k, day_s]
            
            # 最下部に行を追加
            worksheet.append_row(row_data, value_input_option='USER_ENTERED')
            
            # --- 今日のフィードバック計算 ---
            total = am_k + pm_k + day_k + am_s + pm_s + day_s
            cap = FACILITY_CONFIG[facility]["sat"] if date.weekday() == 5 else FACILITY_CONFIG[facility]["week"]
            occ = (total / cap) * 100 if cap > 0 else 0
            
            # --- 今月の累計稼働率と売上予想の計算 ---
            # 入力されたデータをこれまでのデータに結合（メモリ上でシミュレーション）
            new_row_dict = {
                '事業所名': facility, '営業日': date_str,
                '【午前】要介護 利用人数': am_k, '【午前】支援・事業対象 利用人数': am_s,
                '【午後】要介護 利用人数': pm_k, '【午後】支援・事業対象 利用人数': pm_s,
                '【1日型】要介護 利用人数': day_k, '【1日型】支援・事業対象 利用人数': day_s
            }
            if not df_dates.empty:
                df_all = df_dates.copy() # df_datesには全データが入っている前提に変更していますが、カラムが足りないため再取得
                # ※処理速度を優先し、get_all_records の結果を丸ごと再利用できるようにしています
                # ここでは簡易的に、今日のデータだけで月間を概算するのではなく、既存データと結合します
            
            # 再取得して正確に計算する
            df_full = pd.DataFrame(worksheet.get_all_records())
            df_fac = df_full[df_full['事業所名'] == facility].copy()
            df_fac = pd.concat([df_fac, pd.DataFrame([new_row_dict])], ignore_index=True)
            
            # 当月に絞り込み
            target_month = date.strftime('%Y/%m')
            df_fac['営業日_dt'] = pd.to_datetime(df_fac['営業日'])
            df_fac['年月'] = df_fac['営業日_dt'].dt.strftime('%Y/%m')
            df_month = df_fac[df_fac['年月'] == target_month].copy()
            
            # 重複排除（同じ日の最新の報告を残す）
            df_month = df_month.groupby('営業日').tail(1)
            
            # 合計人数の算出
            cols = [c for c in df_month.columns if '人数' in c]
            for c in cols:
                df_month[c] = pd.to_numeric(df_month[c], errors='coerce').fillna(0)
            df_month['合計'] = df_month[cols].sum(axis=1)
            total_users_month = df_month['合計'].sum()
            days_worked = len(df_month)
            
            # 累計定員の算出
            cap_month = 0
            for d_dt in df_month['営業日_dt']:
                if d_dt.weekday() == 5:
                    cap_month += FACILITY_CONFIG[facility]["sat"]
                elif d_dt.weekday() != 6:
                    cap_month += FACILITY_CONFIG[facility]["week"]
                    
            month_occ = (total_users_month / cap_month * 100) if cap_month > 0 else 0
            
            # 今月の営業日数を算出
            import calendar
            _, last_day = calendar.monthrange(date.year, date.month)
            total_biz_days = sum(1 for d in range(1, last_day + 1) if datetime(date.year, date.month, d).weekday() != 6)
            
            st.balloons()
            st.success("✅ スプレッドシートへの保存が完了しました！")
            
            st.markdown(f"""
            <div class="metric-box">
                <div class="sub-text">{date.strftime('%m月%d日')} の本日の稼働率</div>
                <div class="big-number">{occ:.1f}%</div>
                <div class="sub-text" style="margin-bottom: 20px;">本日利用者: <b>{total}</b>人 / 定員: <b>{cap}</b>人</div>
                
                <div style="border-top: 2px dashed #22c55e; margin: 20px 0;"></div>
                
                <div class="sub-text">🏆 今月（{date.month}月）の現在までの累積稼働率</div>
                <div style="font-size: 2.2rem; font-weight: bold; color: #16a34a; margin: 5px 0;">{month_occ:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"エラーが発生しました。詳細: {e}")
