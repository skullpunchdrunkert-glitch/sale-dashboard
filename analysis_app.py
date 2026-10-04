import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import calendar
from datetime import datetime
import io

st.set_page_config(page_title="月次確定 分析ツール", layout="wide", initial_sidebar_state="expanded")




# --- モード選択 ---
mode = st.sidebar.radio("モード選択", ["📝 月次レポート作成", "📊 過去データ閲覧"])
st.sidebar.markdown("---")

if mode == "📊 過去データ閲覧":
    st.title("📊 過去の報告データ閲覧")
    
    FACILITY_CONFIG = {
        "リハビリ教室新松戸": {"week": 84, "sat": 40},
        "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
        "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
        "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
    }
    selected_facility = st.sidebar.selectbox("対象事業所選択", list(FACILITY_CONFIG.keys()), index=2)
    
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        import os
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = None
        if os.path.exists("credentials.json"):
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        elif "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            
        if creds:
            client = gspread.authorize(creds)
            sheet_id = '1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4'
            spreadsheet = client.open_by_key(sheet_id)
            
            ws_name = "管理者会議報告"
            try:
                ws = spreadsheet.worksheet(ws_name)
                records = ws.get_all_records()
                import pandas as pd
                history_df = pd.DataFrame(records)
                
                if not history_df.empty:
                    history_df = history_df[history_df['事業所'] == selected_facility]
                    if not history_df.empty:
                        months = history_df['対象月'].unique().tolist()
                        selected_month = st.selectbox("保存年月を選択", ["すべて"] + months)
                        
                        if selected_month != "すべて":
                            history_df = history_df[history_df['対象月'] == selected_month]
                            
                        st.dataframe(history_df, use_container_width=True)
                        
                        for _, row in history_df.iterrows():
                            st.markdown(f"### {row.get('対象月', '')} の報告")
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**確定総売上:** ¥{row.get('確定総売上', 0):,}")
                                st.markdown(f"**当月着地予測売上:** ¥{row.get('当月着地予測売上', 0):,}")
                            with col_b:
                                st.markdown(f"**前月総合稼働率:** {row.get('前月総合稼働率', '')}")
                                st.markdown(f"**当月累積稼働率:** {row.get('当月累積稼働率', '')}")
                                
                            st.markdown("**営業状況コメント:**")
                            st.info(row.get('営業状況コメント', '（コメントなし）'))
                            
                            st.markdown("**人事・車両・インシデント等の報告:**")
                            st.info(row.get('人事等コメント', '（報告なし）'))
                            
                            st.markdown("---")
                            
                    else:
                        st.info(f"{selected_facility} のデータはまだ保存されていません。")
                else:
                    st.info("スプレッドシートにデータがありません。")
            except gspread.exceptions.WorksheetNotFound:
                st.info("まだスプレッドシートに「管理者会議報告」のデータが保存されていません。（シート未作成）")
        else:
            st.error("認証情報が見つかりません。（Streamlit CloudのSecretsを設定してください）")
            
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        
    st.stop()
with st.sidebar:
    st.header("📁 ファイル取り込み")
    file_sales = st.file_uploader("1. 売上台帳 (前月確定)", type=['csv'])
    file_sched_prev = st.file_uploader("2. スケジュール (前月確定)", type=['csv'])
    file_sched_curr = st.file_uploader("3. スケジュール (当月経過・任意)", type=['csv'])
    
    st.markdown("---")
    st.header("⚙️ 事業所設定")
    FACILITY_CONFIG = {
        "リハビリ教室新松戸": {"week": 84, "sat": 40},
        "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
        "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
        "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
    }
    facility = st.selectbox("対象の事業所名", list(FACILITY_CONFIG.keys()), index=2)
    cap_week = st.number_input("平日定員 (人)", value=FACILITY_CONFIG[facility]["week"], step=1)
    cap_sat = st.number_input("土曜定員 (人)", value=FACILITY_CONFIG[facility]["sat"], step=1)
    target_rate = st.slider("目標稼働率 (%)", 60, 100, 80, 5)

if not file_sales or not file_sched_prev:
    st.info("👈 左側のメニューから、最低限「売上台帳(前月)」と「スケジュール(前月)」のCSVファイルをアップロードしてください。")
    st.stop()

# --- データ解析（前月確定） ---
curr_data_exists = False
try:
    # 1. 売上台帳の解析
    content_sales = file_sales.getvalue().decode('cp932', errors='replace')
    sales_lines = content_sales.split('\n')
    header_idx = 0
    for i, line in enumerate(sales_lines):
        if "利用者氏名" in line and "国保連請求額" in line:
            header_idx = i
            break
            
    df_sales = pd.read_csv(io.StringIO('\n'.join(sales_lines[header_idx:])))
    
    for col in ['国保連請求額', '公費請求額', '利用者負担額', '公費利用者負担額', '限度額超過額', '教材費', '昼食・おやつ・飲み物代', '合計']:
        if col in df_sales.columns:
            df_sales[col] = pd.to_numeric(df_sales[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            
    df_fac_sales = df_sales[(df_sales['事業所名'].astype(str).str.contains(facility, na=False)) & (df_sales['サービス種類'] == '利用者合計')]
    if df_fac_sales.empty:
        df_fac_sales = df_sales[df_sales['サービス種類'] == '利用者合計']
        
    ins_cols = ['国保連請求額', '公費請求額', '利用者負担額', '公費利用者負担額']
    self_cols = ['限度額超過額', '教材費', '昼食・おやつ・飲み物代']
    
    insurance_sales = df_fac_sales[ins_cols].sum().sum() if set(ins_cols).issubset(df_fac_sales.columns) else 0
    selfpay_sales = df_fac_sales[self_cols].sum().sum() if set(self_cols).issubset(df_fac_sales.columns) else 0
    confirmed_sales = df_fac_sales['合計'].sum() if '合計' in df_fac_sales.columns else (insurance_sales + selfpay_sales)

    if confirmed_sales == 0:
        st.warning("売上台帳から該当事業所の売上データが取得できませんでした。0円として計算します。")

except Exception as e:
    import traceback
    traceback.print_exc()
    st.error(f"【売上台帳】のファイル読み込み中にエラーが発生しました。詳細: {e}")
    st.stop()

try:
    # 2. スケジュール(前月)の解析
    sched_p_lines = file_sched_prev.getvalue().decode('cp932', errors='replace').split('\n')
    header_idx_p = 0
    for i, line in enumerate(sched_p_lines):
        if "サービス日付" in line or "利用者氏名" in line:
            header_idx_p = i
            break
    df_prev = pd.read_csv(io.StringIO('\n'.join(sched_p_lines[header_idx_p:])))
    
    col_prev = 'サービス実績' if 'サービス実績' in df_prev.columns else (df_prev.columns[258] if len(df_prev.columns) > 258 else None)
    if col_prev:
        actual_vals_p = pd.to_numeric(df_prev[col_prev], errors='coerce').fillna(0)
        df_prev = df_prev[actual_vals_p != 0]
        
    df_prev['サービス日付'] = pd.to_datetime(df_prev['サービス日付'], errors='coerce')
    df_prev = df_prev.dropna(subset=['サービス日付'])
    
    
    care_col = next((c for c in df_prev.columns if '介護度' in c or '要介護' in c), None)
    if care_col:
        care_count = df_prev[care_col].astype(str).str.contains('要介護').sum()
        support_count = df_prev[care_col].astype(str).str.contains('支援|対象|事業').sum()
        total_valid = care_count + support_count
        if total_valid > 0:
            care_ratio = care_count / total_valid * 100
            support_ratio = support_count / total_valid * 100
            ratio_str = f"要介護 {care_ratio:.1f}% &nbsp;/&nbsp; 要支援等 {support_ratio:.1f}%"
        else:
            ratio_str = "データなし"
    else:
        ratio_str = "データなし"
        
    daily_prev = df_prev.groupby('サービス日付').size().reset_index(name='利用者数')
    daily_prev['曜日'] = daily_prev['サービス日付'].dt.dayofweek
    
    prev_month_dt = daily_prev['サービス日付'].max()
    month_str = prev_month_dt.strftime('%Y年%m月')
    yr_p, mo_p = prev_month_dt.year, prev_month_dt.month
    
    total_users_p = daily_prev['利用者数'].sum()
    days_week_p = len(daily_prev[daily_prev['曜日'] <= 4])
    days_sat_p = len(daily_prev[daily_prev['曜日'] == 5])
    total_days_p = days_week_p + days_sat_p
    
    users_week_p = daily_prev[daily_prev['曜日'] <= 4]['利用者数'].sum()
    users_sat_p = daily_prev[daily_prev['曜日'] == 5]['利用者数'].sum()
    
    avg_total_p = total_users_p / total_days_p if total_days_p > 0 else 0
    avg_week_p = users_week_p / days_week_p if days_week_p > 0 else 0
    avg_sat_p = users_sat_p / days_sat_p if days_sat_p > 0 else 0
    
    cap_week_total_p = days_week_p * cap_week
    cap_sat_total_p = days_sat_p * cap_sat
    
    occ_week_p = (users_week_p / cap_week_total_p * 100) if cap_week_total_p > 0 else 0
    occ_sat_p = (users_sat_p / cap_sat_total_p * 100) if cap_sat_total_p > 0 else 0
    
    unit_price = confirmed_sales / total_users_p if total_users_p > 0 else 0
except Exception as e:
    import traceback
    traceback.print_exc()
    st.error(f"【前月スケジュール】のファイル読み込み中にエラーが発生しました。詳細: {e}")
    st.stop()
    
try:
    # 3. スケジュール(当月)の解析
    if file_sched_curr:
        sched_c_lines = file_sched_curr.getvalue().decode('cp932', errors='replace').split('\n')
        header_idx_c = 0
        for i, line in enumerate(sched_c_lines):
            if "サービス日付" in line or "利用者氏名" in line:
                header_idx_c = i
                break
        df_curr = pd.read_csv(io.StringIO('\n'.join(sched_c_lines[header_idx_c:])))
        
        col_curr = 'サービス予定' if 'サービス予定' in df_curr.columns else (df_curr.columns[258] if len(df_curr.columns) > 258 else None)
        if col_curr:
            plan_vals_c = pd.to_numeric(df_curr[col_curr], errors='coerce').fillna(0)
            df_curr = df_curr[plan_vals_c != 0]
            
        df_curr['サービス日付'] = pd.to_datetime(df_curr['サービス日付'], errors='coerce')
        df_curr = df_curr.dropna(subset=['サービス日付'])
        
        daily_curr = df_curr.groupby('サービス日付').size().reset_index(name='予定者数')
        daily_curr['曜日'] = daily_curr['サービス日付'].dt.dayofweek
        
        curr_month_dt = daily_curr['サービス日付'].max()
        curr_month_str = curr_month_dt.strftime('%Y年%m月')
        
        total_users_c = daily_curr['予定者数'].sum()
        days_week_c = len(daily_curr[daily_curr['曜日'] <= 4])
        days_sat_c = len(daily_curr[daily_curr['曜日'] == 5])
        
        users_week_c = daily_curr[daily_curr['曜日'] <= 4]['予定者数'].sum()
        users_sat_c = daily_curr[daily_curr['曜日'] == 5]['予定者数'].sum()
        
        cap_week_total_c = days_week_c * cap_week
        cap_sat_total_c = days_sat_c * cap_sat
        
        occ_week_c = (users_week_c / cap_week_total_c * 100) if cap_week_total_c > 0 else 0
        occ_sat_c = (users_sat_c / cap_sat_total_c * 100) if cap_sat_total_c > 0 else 0
        
        forecast_sales = total_users_c * unit_price
        
        total_days_c = days_week_c + days_sat_c
        curr_data_exists = True
        
        import calendar
        _, last_day_c = calendar.monthrange(curr_month_dt.year, curr_month_dt.month)
        total_biz_days_c = sum(1 for d in range(1, last_day_c + 1) if datetime(curr_month_dt.year, curr_month_dt.month, d).weekday() <= 5)
        avg_total_c = total_users_c / (days_week_c + days_sat_c) if (days_week_c + days_sat_c) > 0 else 0
        avg_week_c = users_week_c / days_week_c if days_week_c > 0 else 0
        avg_sat_c = users_sat_c / days_sat_c if days_sat_c > 0 else 0

        projected_users_c = avg_total_c * total_biz_days_c
        projected_sales_c = projected_users_c * unit_price
        
        occ_c_total = (total_users_c / (cap_week_total_c + cap_sat_total_c) * 100) if (cap_week_total_c + cap_sat_total_c) > 0 else 0
    else:
        curr_month_str = "当月"
        occ_week_c = occ_sat_c = forecast_sales = total_users_c = 0
        users_week_c = users_sat_c = cap_week_total_c = cap_sat_total_c = 0
except Exception as e:
    import traceback
    traceback.print_exc()
    st.error(f"【当月スケジュール】のファイル読み込み中にエラーが発生しました。詳細: {e}")
    st.stop()




# --- UI 1ページ目 ---

# --- CSS for Print and Styling ---
st.markdown("""
<style>
@media print {
    /* Set page to A4 portrait and scale down to ensure everything fits */
    
    @page { size: A4 portrait; margin: 5mm; }
    
    /* Force all containers to allow overflow so Plotly doesn't clip */
    .stApp, .block-container, [data-testid="stAppViewBlockContainer"], 
    [data-testid="stVerticalBlock"], [data-testid="column"], 
    .element-container, .stPlotlyChart {
        overflow: visible !important;
    }
    
    body { zoom: 0.68 !important; }
    
    .stApp, [data-testid="stAppViewBlockContainer"], .block-container {
        max-width: 100% !important;
        width: 100% !important;
        padding: 10px !important;
    }
    
    [data-testid="column"] {
        flex: 1 1 0% !important;
    }
    
    /* Scale Plotly charts so they never clip, and align them to the right */
    .stPlotlyChart {
        
        transform-origin: top right !important;
        max-width: none !important;
    }

    /* Hide sidebar, buttons, and specific iframes (PDF button) */
    [data-testid="stSidebar"], .stButton, .no-print, iframe {
        display: none !important;
    }
    
    /* Hide the parent containers of the iframe if possible */
    .element-container:has(iframe) { display: none !important; }
}

div.stMarkdown {
    font-size: 1.15rem;
}
div[data-baseweb="textarea"] textarea {
    font-size: 1.35rem !important;
    line-height: 1.4 !important;
}
.report-title {
    font-size: 1.95rem !important;
    font-weight: bold;
    color: #1E293B;
}
.section-title {
    font-size: 1.45rem !important;
    font-weight: bold;
    background-color: #E2E8F0;
    padding: 6px 12px;
    border-left: 6px solid #3B82F6;
    margin-top: 15px;
    margin-bottom: 10px;
    color: #0F172A;
}
.kpi-main {
    font-size: 1.6rem !important;
    font-weight: bold;
    color: #1E293B;
}
.kpi-sales {
    font-size: 1.9rem !important;
    color: #EF4444 !important;
}
</style>
""", unsafe_allow_html=True)

cap_week_80 = cap_week * 0.8
cap_sat_80 = cap_sat * 0.8

st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 3px solid #3B82F6; padding-bottom: 8px; margin-bottom: 12px;">
    <div>
        <div class="report-title" style="border: none; padding: 0; margin: 0;">{month_str} 管理者会議報告</div>
        <div style="font-size: 1.5rem; font-weight: bold; color: #334155; margin-top: 8px;">{facility}</div>
    </div>
    <div>
        <table style="border-collapse: collapse; text-align: center; font-size: 1.05rem; font-weight: bold; color: #1E293B; margin-bottom: 3px;">
            <tr>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; background: #F1F5F9;">定員</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; background: #F1F5F9;">平日</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; background: #F1F5F9;">土曜</td>
            </tr>
            <tr>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; background: #F8FAFC;">設定</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1;">{cap_week}名</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1;">{cap_sat}名</td>
            </tr>
            <tr>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; background: #FEE2E2; color:#EF4444;">8割目標</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; color:#EF4444;">{cap_week_80:.1f}名</td>
                <td style="padding: 3px 12px; border: 1px solid #CBD5E1; color:#EF4444;">{cap_sat_80:.1f}名</td>
            </tr>
        </table>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f'<div class="section-title" style="margin-top: 0px;">1. 前月（確定）の営業報告 &nbsp;&nbsp;&nbsp; 営業日数 {total_days_p} 日</div>', unsafe_allow_html=True)

# 60% : 40% (Make left wider to avoid wrap, right narrower to push right)
col1, col2 = st.columns([1.3, 1.0])

with col1:
    st.markdown(f"""<div style="margin-left:10px; line-height: 1.7; font-size: 1.15rem;">
<div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_p:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {users_week_p:,.0f} 人 &nbsp;&nbsp; 土曜 {users_sat_p:,.0f} 人)</div>
<div>1日平均利用 &nbsp;&nbsp; <span class="kpi-main">{avg_total_p:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {avg_week_p:.2f} 人 &nbsp;&nbsp; 土曜 {avg_sat_p:.2f} 人)</div>
<div>稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline; font-weight:bold;">{occ_week_p:.2f} %</span> &nbsp;&nbsp; 土曜 <span style="text-decoration:underline; font-weight:bold;">{occ_sat_p:.2f} %</span>)</div>
<div style="margin-top: 4px; color:#475569;">要介護・要支援（事業対象含む）割合 &nbsp;&nbsp; <span style="font-weight:bold; color:#1E293B;">{ratio_str if 'ratio_str' in locals() else 'データなし'}</span></div>
<div style="margin-top: 15px; padding-top: 15px; border-top: 2px dashed #CBD5E1;">
<div style="font-size: 1.25rem; font-weight: bold; color: #0F172A; margin-bottom: 5px;">確定総売上 &nbsp;&nbsp; <span class="kpi-main kpi-sales">¥{confirmed_sales:,.0f}</span></div>
<div style="margin-left: 10px; color: #475569; line-height: 1.3; font-size: 1.05rem;">・介護保険請求額: ¥{insurance_sales:,.0f}<br>・自費請求額: ¥{selfpay_sales:,.0f}</div>
<div style="margin-top: 12px;">確定客単価 &nbsp;&nbsp; <span class="kpi-main">¥{unit_price:,.0f}</span></div>
</div></div>""", unsafe_allow_html=True)

    total_cap_p = cap_week_total_p + cap_sat_total_p
    sales_80 = total_cap_p * 0.8 * unit_price
    sales_85 = total_cap_p * 0.85 * unit_price
    diff_80 = confirmed_sales - sales_80
    diff_85 = confirmed_sales - sales_85
    
    color_80 = "red" if diff_80 < 0 else "blue"
    color_85 = "red" if diff_85 < 0 else "blue"
    sign_80 = "" if diff_80 < 0 else "+"
    sign_85 = "" if diff_85 < 0 else "+"
    
    st.markdown(f"""<div style="margin-top: 15px; padding: 12px; background-color: #F8FAFC; border-radius: 8px; border: 1px solid #E2E8F0;">
<div style="font-weight: bold; margin-bottom: 5px; font-size: 1.15rem;">目標稼働率との売上差額（実績ベース）</div>
<div style="font-size: 1.1rem; line-height: 1.5;">
稼働率 80.0% の場合: <span style="color: {color_80}; font-weight:bold;">{sign_80}¥{diff_80:,.0f}</span> (目標 ¥{sales_80:,.0f})<br>
稼働率 85.0% の場合: <span style="color: {color_85}; font-weight:bold;">{sign_85}¥{diff_85:,.0f}</span> (目標 ¥{sales_85:,.0f})
</div></div>""", unsafe_allow_html=True)

with col2:
    import plotly.graph_objects as go
    if not daily_prev.empty:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=daily_prev['サービス日付'], y=daily_prev['利用者数'], mode='lines+markers', line=dict(color='#2563EB', width=3), name='利用者数'))
        
        target_80_y = [cap_sat * 0.8 if d.weekday() == 5 else cap_week * 0.8 for d in daily_prev['サービス日付']]
        fig1.add_trace(go.Scatter(x=daily_prev['サービス日付'], y=target_80_y, mode='lines', line=dict(color='red', dash='dash', width=2), name='8割ライン'))
        
        fig1.update_layout(title=dict(text='日別利用者数推移（確定月）', font=dict(size=16)), height=250, margin=dict(l=5,r=5,t=25,b=10), yaxis=dict(range=[0, max(cap_week, cap_sat)+5]), legend=dict(orientation="h", y=-0.2, yanchor="bottom", xanchor="right", x=1))
        fig1.update_layout(width=420)
        st.plotly_chart(fig1, use_container_width=False, config={'displayModeBar': False})
        
        wd_map = {0: '月', 1: '火', 2: '水', 3: '木', 4: '金', 5: '土'}
        df_wd = daily_prev[daily_prev['曜日'] <= 5].copy()
        if not df_wd.empty:
            wd_agg = df_wd.groupby('曜日').agg(
                users=('利用者数', 'sum'),
                days=('利用者数', 'count')
            ).reset_index()
            
            wd_agg['cap_total'] = wd_agg.apply(lambda r: r['days'] * (cap_sat if r['曜日'] == 5 else cap_week), axis=1)
            wd_agg['occ'] = (wd_agg['users'] / wd_agg['cap_total']) * 100
            wd_agg['wd_name'] = wd_agg['曜日'].map(wd_map)
            
            fig2 = go.Figure(data=[go.Bar(
                x=wd_agg['wd_name'], 
                y=wd_agg['occ'], 
                marker_color='#10B981',
                text=[f'{val:.1f}%' for val in wd_agg['occ']],
                textposition='auto',
                textfont=dict(size=15, color='white', weight='bold')
            )])
            fig2.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="8割ライン", annotation_position="top right")
            fig2.update_layout(title=dict(text='曜日別稼働率（%）', font=dict(size=16)), height=250, margin=dict(l=5,r=5,t=25,b=10), yaxis=dict(range=[0, 110]))
            fig2.update_layout(width=420)
        st.plotly_chart(fig2, use_container_width=False, config={'displayModeBar': False})


if curr_data_exists:
    st.markdown(f'<div class="section-title" style="margin-top: 10px;">2. 当月（会議当月）の営業経過・着地予想 &nbsp;&nbsp;&nbsp; 経過日数 {total_days_c} 日</div>', unsafe_allow_html=True)
    st.markdown(f"""<div style="margin-left:10px; line-height: 1.6; font-size: 1.15rem;">
<div>現在までののべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_c:,.0f}</span> 人 &nbsp;&nbsp; / &nbsp;&nbsp; 1日平均利用 &nbsp;&nbsp; <span class="kpi-main">{avg_total_c:.2f}</span> 人 <span style="font-size:1.05rem;">(平日 {avg_week_c:.2f} 人 &nbsp; 土曜 {avg_sat_c:.2f} 人)</span></div>
<div style="margin-top: 6px;">累積稼働率 &nbsp;&nbsp; <span class="kpi-main">{occ_c_total:.2f} %</span> &nbsp;&nbsp; <span style="font-size:1.05rem;">(平日 <span style="text-decoration:underline; font-weight:bold;">{occ_week_c:.2f} %</span> &nbsp; 土曜 <span style="text-decoration:underline; font-weight:bold;">{occ_sat_c:.2f} %</span>)</span></div>
<div style="margin-top: 10px; display: flex; align-items: flex-end;">
<div>当月の売上着地予想 &nbsp;&nbsp; <span class="kpi-main kpi-sales">約 ¥{projected_sales_c:,.0f}</span></div>
<div style="font-size: 0.95rem; color:#64748B; margin-bottom:3px; margin-left: 15px;">※前月の確定客単価 (¥{unit_price:,.0f}) × 当月の着地予想人数 ({projected_users_c:,.0f}人)</div>
</div></div>""", unsafe_allow_html=True)
    
st.markdown('<div style="font-weight:bold; font-size:1.15rem; color:#0F172A; border-bottom:2px solid #CBD5E1; margin-top:15px; margin-bottom:5px;">前月・今月の営業状況コメント</div>', unsafe_allow_html=True)
# Reduced height to prevent Page 1 overflow
comment_text = st.text_area("", placeholder="前月の総括や、今月の見込み・共有事項を入力してください...", height=120, label_visibility="collapsed", key="report_comment")

st.markdown('<div class="section-title" style="margin-top: 15px;">3. 人事・車両・インシデントなどの報告</div>', unsafe_allow_html=True)
incident_comment = st.text_area("", placeholder="人事異動、車両の状況、ヒヤリハット・インシデント等の共有事項を入力してください...", height=120, label_visibility="collapsed", key="incident_comment")

# Move "次回会議日程" to the bottom right of Page 1
st.markdown('<div style="text-align: right; font-weight:bold; font-size:1.3rem; margin-top:20px; margin-bottom:10px;">次回会議日程　　　　月　　　日　（　　　）　　～　</div>', unsafe_allow_html=True)

# --- UI 2ページ目 ---
st.markdown('<div style="page-break-before: always; height:0;"></div>', unsafe_allow_html=True)
st.markdown('<div style="margin-top: 35px;"></div>', unsafe_allow_html=True)

st.markdown(f'<div class="page2-title" style="font-size: 1.5rem; font-weight: bold; border-bottom: 2px solid #3B82F6; margin-bottom: 12px;">{facility} 日々実績データ（確定月・当月比較）</div>', unsafe_allow_html=True)

df_dict_p = {}
if not daily_prev.empty:
    for _, r in daily_prev.iterrows():
        df_dict_p[r['サービス日付'].day] = r['利用者数']
        
df_dict_c = {}
if curr_data_exists and not daily_curr.empty:
    for _, r in daily_curr.iterrows():
        df_dict_c[r['サービス日付'].day] = r['予定者数']

wd_str = ["月", "火", "水", "木", "金", "土", "日"]

html_table = f"""
<table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 1.05rem; margin-bottom: 25px;">
    <tr style="background-color: #F1F5F9; border: 1px solid #CBD5E1;">
        <th colspan="4" style="padding: 6px; border: 1px solid #CBD5E1; font-size: 1.15rem;">【確定月】{mo_p}月</th>
        <th colspan="4" style="padding: 6px; border: 1px solid #CBD5E1; background-color: #F0FDF4; font-size: 1.15rem;">【当月】{curr_month_dt.month if curr_data_exists else '-'}月</th>
    </tr>
    <tr style="background-color: #F8FAFC; border: 1px solid #CBD5E1;">
        <th style="border: 1px solid #CBD5E1; width: 8%; padding: 4px;">日付</th>
        <th style="border: 1px solid #CBD5E1; width: 7%; padding: 4px;">曜日</th>
        <th style="border: 1px solid #CBD5E1; width: 10%; padding: 4px;">利用者数</th>
        <th style="border: 1px solid #CBD5E1; width: 15%; padding: 4px;">稼働率</th>
        <th style="border: 1px solid #CBD5E1; width: 8%; background-color: #F0FDF4; padding: 4px;">日付</th>
        <th style="border: 1px solid #CBD5E1; width: 7%; background-color: #F0FDF4; padding: 4px;">曜日</th>
        <th style="border: 1px solid #CBD5E1; width: 10%; background-color: #F0FDF4; padding: 4px;">利用者数</th>
        <th style="border: 1px solid #CBD5E1; width: 15%; background-color: #F0FDF4; padding: 4px;">稼働率</th>
    </tr>
"""

import calendar
from datetime import date
_, last_day_p = calendar.monthrange(yr_p, mo_p)
if curr_data_exists:
    _, last_day_c = calendar.monthrange(curr_month_dt.year, curr_month_dt.month)
else:
    last_day_c = 0

max_days = max(last_day_p, last_day_c)

row_count = 0
for day in range(1, max_days + 1):
    p_date_html = ""
    p_wd_html = ""
    p_users_html = ""
    p_occ_html = ""
    
    if day <= last_day_p:
        try:
            dt_p = date(yr_p, mo_p, day)
            w_p = dt_p.weekday()
            if w_p != 6:
                cap = cap_sat if w_p == 5 else cap_week
                users = df_dict_p.get(day, "")
                occ_str = ""
                cls_str = ""
                if users != "":
                    occ = (users / cap) * 100
                    occ_str = f"{occ:.2f}%"
                    if occ >= target_rate:
                        cls_str = ' style="font-weight:bold; color:#10B981;"'
                p_date_html = f"{mo_p}/{day}"
                p_wd_html = wd_str[w_p]
                p_users_html = str(users)
                p_occ_html = f"<span{cls_str}>{occ_str}</span>"
        except ValueError:
            pass
            
    c_date_html = ""
    c_wd_html = ""
    c_users_html = ""
    c_occ_html = ""
    
    if curr_data_exists and day <= last_day_c:
        try:
            dt_c = date(curr_month_dt.year, curr_month_dt.month, day)
            w_c = dt_c.weekday()
            if w_c != 6:
                cap = cap_sat if w_c == 5 else cap_week
                users = df_dict_c.get(day, "")
                occ_str = ""
                cls_str = ""
                if users != "":
                    occ = (users / cap) * 100
                    occ_str = f"{occ:.2f}%"
                    if occ >= target_rate:
                        cls_str = ' style="font-weight:bold; color:#10B981;"'
                c_date_html = f"{curr_month_dt.month}/{day}"
                c_wd_html = wd_str[w_c]
                c_users_html = str(users)
                c_occ_html = f"<span{cls_str}>{occ_str}</span>"
        except ValueError:
            pass
            
    if p_date_html != "" or c_date_html != "":
        html_table += f"<tr><td style='border: 1px solid #CBD5E1; padding: 2px;'>{p_date_html}</td><td style='border: 1px solid #CBD5E1; padding: 2px;'>{p_wd_html}</td><td style='border: 1px solid #CBD5E1; padding: 2px;'>{p_users_html}</td><td style='border: 1px solid #CBD5E1; padding: 2px;'>{p_occ_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC; padding: 2px;'>{c_date_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC; padding: 2px;'>{c_wd_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC; padding: 2px;'>{c_users_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC; padding: 2px;'>{c_occ_html}</td></tr>"

html_table += "</table>"
st.markdown(html_table, unsafe_allow_html=True)


# --- 曜日別稼働率の比較表 ---
if curr_data_exists:
    st.markdown('<div style="font-size:1.25rem; font-weight:bold; margin-top:20px; color:#1E293B; margin-bottom: 10px;">確定月と当月の「曜日別稼働率」比較表</div>', unsafe_allow_html=True)
    
    wd_agg_c = None
    df_wd_c = daily_curr[daily_curr['曜日'] <= 5].copy()
    if not df_wd_c.empty:
        wd_agg_c = df_wd_c.groupby('曜日').agg(
            users=('予定者数', 'sum'),
            days=('予定者数', 'count')
        ).reset_index()
        wd_agg_c['cap_total'] = wd_agg_c.apply(lambda r: r['days'] * (cap_sat if r['曜日'] == 5 else cap_week), axis=1)
        wd_agg_c['occ'] = (wd_agg_c['users'] / wd_agg_c['cap_total']) * 100
        wd_dict_c = dict(zip(wd_agg_c['曜日'], wd_agg_c['occ']))
    else:
        wd_dict_c = {}
        
    wd_dict_p = dict(zip(wd_agg['曜日'], wd_agg['occ'])) if 'wd_agg' in locals() and not wd_agg.empty else {}
    
    comp_html = """
    <table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 1.05rem; margin-bottom: 25px;">
        <tr style="background-color: #E2E8F0; border: 1px solid #CBD5E1;">
            <th style="padding: 8px; border: 1px solid #CBD5E1;"></th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">月曜日</th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">火曜日</th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">水曜日</th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">木曜日</th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">金曜日</th>
            <th style="padding: 8px; border: 1px solid #CBD5E1;">土曜日</th>
        </tr>
    """
    
    comp_html += f"<tr><td style='border: 1px solid #CBD5E1; font-weight:bold; background-color: #F8FAFC; padding: 6px;'>【{mo_p}月実績】</td>"
    for w in range(6):
        occ = wd_dict_p.get(w, 0)
        cls_str = ' style="border: 1px solid #CBD5E1; font-weight:bold; color: #EF4444; background-color: #FEE2E2; padding: 6px;"' if occ >= 80 else ' style="border: 1px solid #CBD5E1; padding: 6px;"'
        comp_html += f"<td{cls_str}>{occ:.1f}%</td>"
    comp_html += "</tr>"
    
    cur_mo_str = curr_month_dt.month if curr_data_exists else '-'
    comp_html += f"<tr><td style='border: 1px solid #CBD5E1; font-weight:bold; background-color: #F0FDF4; padding: 6px;'>【{cur_mo_str}月予測】</td>"
    for w in range(6):
        occ = wd_dict_c.get(w, 0)
        cls_str = ' style="border: 1px solid #CBD5E1; font-weight:bold; color: #EF4444; background-color: #FEE2E2; padding: 6px;"' if occ >= 80 else ' style="border: 1px solid #CBD5E1; padding: 6px;"'
        comp_html += f"<td{cls_str}>{occ:.1f}%</td>"
    comp_html += "</tr></table>"
    
    st.markdown(comp_html, unsafe_allow_html=True)


st.markdown('<div class="no-print" style="margin-top:20px;"></div>', unsafe_allow_html=True)

st.markdown("""
<style>
div.stButton > button {
    font-size: 1.1rem !important;
    font-weight: bold !important;
    height: 54px !important;
    border-radius: 8px !important;
    width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("💾 データ保存", type="primary", use_container_width=True):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            import os
            
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = None
            if os.path.exists("credentials.json"):
                creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
            elif "gcp_service_account" in st.secrets:
                creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
                
            if creds:
                client = gspread.authorize(creds)
                sheet_id = '1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4'
                spreadsheet = client.open_by_key(sheet_id)
                
                ws_name = "管理者会議報告"
                try:
                    ws = spreadsheet.worksheet(ws_name)
                except gspread.exceptions.WorksheetNotFound:
                    ws = spreadsheet.add_worksheet(title=ws_name, rows="1000", cols="20")
                    headers = ['報告日時', '対象月', '事業所', '確定総売上', '前月総合稼働率', '前月平日稼働率', '前月土曜稼働率', '当月着地予測売上', '当月累積稼働率', '営業状況コメント', '人事等コメント']
                    ws.append_row(headers)
                
                records = ws.get_all_records()
                header_row = ws.row_values(1)
                if '人事等コメント' not in header_row:
                    ws.update_cell(1, len(header_row) + 1, '人事等コメント')
                
                row_to_update = None
                for i, record in enumerate(records):
                    if str(record.get('対象月', '')) == str(month_str) and str(record.get('事業所', '')) == str(facility):
                        row_to_update = i + 2
                        break
                        
                from datetime import datetime as dt_now
                now_str = dt_now.now().strftime("%Y-%m-%d %H:%M:%S")
                
                new_row = [
                    now_str,
                    month_str,
                    facility,
                    confirmed_sales,
                    f"{(occ_week_p*days_week_p + occ_sat_p*days_sat_p)/total_days_p if total_days_p>0 else 0:.2f}%",
                    f"{occ_week_p:.2f}%",
                    f"{occ_sat_p:.2f}%",
                    projected_sales_c if curr_data_exists else 0,
                    f"{occ_c_total:.2f}%" if curr_data_exists else "0%",
                    comment_text,
                    incident_comment
                ]
                
                if row_to_update:
                    ws.update(f"A{row_to_update}:K{row_to_update}", [new_row])
                    st.success(f"スプレッドシートの {month_str}・{facility} のデータを上書き更新しました！")
                else:
                    ws.append_row(new_row)
                    st.success(f"スプレッドシートへ {month_str}・{facility} のデータを新規保存しました！")
            else:
                st.error("認証情報(credentials.json)が見つかりません。")
        except Exception as e:
            st.error(f"スプレッドシート送信エラー: {e}")

with col_btn2:
    import streamlit.components.v1 as components
    components.html("""
        <div class="no-print" style="text-align: center;">
            <button style="width: 100%; height: 54px; background-color: #3B82F6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
            onclick="window.parent.print();">
                🖨️ PDFに出力する（印刷）
            </button>
        </div>
    """, height=70)

st.markdown("""
<div class="no-print">
<p style="font-size: 0.95rem; color: #64748B; margin-top: 2px; text-align: right;">
    ※ Chrome等のブラウザの印刷機能を使用します。<br>
    ※ 「送信先」を「PDFに保存」に設定し、レイアウトを「縦」にして保存してください。<br>
    ※ 「背景のグラフィック」にチェックを入れると色が綺麗に印刷されます。<br>
    ※ グラフが切れる場合は、印刷設定の「倍率（スケール）」を調整してください。
</p>
</div>
""", unsafe_allow_html=True)
