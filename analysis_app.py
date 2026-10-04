import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import calendar
from datetime import datetime
import io
import os
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="月次確定 分析ツール", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .report-title { font-size: 1.6rem; font-weight: bold; border-bottom: 2px solid #2dce89; padding-bottom: 3px; margin-bottom: 5px; color: #1f2937; }
    .section-title { font-size: 1.15rem; font-weight: bold; background-color: #e2e8f0; padding: 2px 10px; border-left: 5px solid #475569; margin-top: 4px; margin-bottom: 2px; color: #1e293b; }
    .kpi-main { font-size: 1.15rem; font-weight: bold; color: #0f172a; }
    .sales-highlight { font-size: 1.35rem; font-weight: bold; color: #0f172a; border-bottom: 2px solid #2dce89; padding-bottom: 2px; }
    .page2-title { font-size: 1.6rem; font-weight: bold; text-align: left; }
    .page2-header-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-bottom: 2px; }
    .page2-header-table td { padding: 4px 10px; text-align: center; }
    .page2-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; margin-bottom: 10px; }
    .page2-table th, .page2-table td { border: 1px solid #111; padding: 2px; text-align: center; height: 28px; }
    .page2-table th { background-color: #f8fafc; font-weight: 600; }
    .target-ok { background-color: #bbf7d0 !important; font-weight: bold; }
    .summary-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 5px; }
    .summary-table th, .summary-table td { border: 1px solid #111; padding: 4px; text-align: center; }
    @media print {
        .no-print { display: none !important; }
        @page { size: A4 portrait; margin: 0; }
        body { zoom: 0.85 !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        header, .stSidebar, .stToolbar, footer { display: none !important; }
        .element-container:has(iframe) { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
        iframe { display: none !important; }
        .block-container { padding: 12mm 10mm !important; margin: 0 !important; max-width: 100% !important; width: 100% !important; }
    }
</style>
""", unsafe_allow_html=True)

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
try:
    # 1. 売上台帳の解析
    content_sales = file_sales.getvalue().decode('cp932', errors='replace')
    sales_lines = content_sales.split('\n')
    confirmed_sales = 0
    for line in reversed(sales_lines):
        if "事業所合計" in line:
            parts = line.split(',')
            try:
                confirmed_sales = int(parts[-1].replace('"', '').replace(',', ''))
                break
            except:
                pass

    # 2. スケジュール(前月)の解析
    df_prev = pd.read_csv(io.StringIO(file_sched_prev.getvalue().decode('cp932', errors='replace')))
    
    # --- 実績0（欠席など）のデータを除外 ---
    col_prev = 'サービス実績' if 'サービス実績' in df_prev.columns else (df_prev.columns[258] if len(df_prev.columns) > 258 else None)
    if col_prev:
        actual_vals_p = pd.to_numeric(df_prev[col_prev], errors='coerce').fillna(0)
        df_prev = df_prev[actual_vals_p != 0]
        
    df_prev['サービス日付'] = pd.to_datetime(df_prev['サービス日付'], errors='coerce')
    df_prev = df_prev.dropna(subset=['サービス日付'])
    
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
    st.error(f"前月ファイルの読み込み中にエラーが発生しました。詳細: {e}")
    st.stop()

# --- データ解析（当月経過） ---
curr_data_exists = False
if file_sched_curr:
    try:
        df_curr = pd.read_csv(io.StringIO(file_sched_curr.getvalue().decode('cp932', errors='replace')))
        
        # --- 実績0（欠席など）のデータを除外 ---
        col_curr = 'サービス実績' if 'サービス実績' in df_curr.columns else (df_curr.columns[258] if len(df_curr.columns) > 258 else None)
        if col_curr:
            actual_vals_c = pd.to_numeric(df_curr[col_curr], errors='coerce').fillna(0)
            df_curr = df_curr[actual_vals_c != 0]
            
        df_curr['サービス日付'] = pd.to_datetime(df_curr['サービス日付'], errors='coerce')
        df_curr = df_curr.dropna(subset=['サービス日付'])
        
        daily_curr = df_curr.groupby('サービス日付').size().reset_index(name='利用者数')
        daily_curr['曜日'] = daily_curr['サービス日付'].dt.dayofweek
        
        if not daily_curr.empty:
            curr_month_dt = daily_curr['サービス日付'].max()
            yr_c, mo_c = curr_month_dt.year, curr_month_dt.month
            
            total_users_c = daily_curr['利用者数'].sum()
            days_week_c = len(daily_curr[daily_curr['曜日'] <= 4])
            days_sat_c = len(daily_curr[daily_curr['曜日'] == 5])
            total_days_c = days_week_c + days_sat_c
            
            users_week_c = daily_curr[daily_curr['曜日'] <= 4]['利用者数'].sum()
            users_sat_c = daily_curr[daily_curr['曜日'] == 5]['利用者数'].sum()
            
            avg_total_c = total_users_c / total_days_c if total_days_c > 0 else 0
            
            cap_week_total_c = days_week_c * cap_week
            cap_sat_total_c = days_sat_c * cap_sat
            occ_c_total = (total_users_c / (cap_week_total_c + cap_sat_total_c) * 100) if (cap_week_total_c + cap_sat_total_c) > 0 else 0
            
            # 当月の総営業日数を計算して着地予想
            _, last_day_c = calendar.monthrange(yr_c, mo_c)
            total_biz_days_c = sum(1 for d in range(1, last_day_c + 1) if datetime(yr_c, mo_c, d).weekday() != 6)
            
            projected_users_c = avg_total_c * total_biz_days_c
            projected_sales_c = projected_users_c * unit_price
            
            curr_data_exists = True
    except Exception as e:
        st.warning(f"当月スケジュールの読み込みに失敗しました。無視して前月データのみ表示します。詳細: {e}")

# --- UI 描画（1ページ目） ---
st.markdown(f'''
<div class="report-title" style="display: flex; justify-content: space-between; align-items: baseline;">
    <div>{month_str} 確定分析レポート &nbsp;&nbsp;&nbsp; {facility}</div>
    <div style="font-size: 1.15rem; color: #475569; font-weight: bold;">【定員】平日: {cap_week}人 / 土曜: {cap_sat}人</div>
</div>
''', unsafe_allow_html=True)

cap_total_p = cap_week_total_p + cap_sat_total_p
sales_80_p = cap_total_p * 0.8 * unit_price
sales_85_p = cap_total_p * 0.85 * unit_price
diff_80_p = confirmed_sales - sales_80_p
color_80_p = "#16a34a" if diff_80_p >= 0 else "#ef4444"
sign_80_p = "+" if diff_80_p >= 0 else ""

st.markdown(f'<div class="section-title">１．前月の営業報告（確定値） &nbsp;&nbsp;&nbsp; 営業日数 {total_days_p} 日</div>', unsafe_allow_html=True)
st.markdown(f"""
<div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
    <div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_p:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {users_week_p:,.0f} 人 &nbsp;&nbsp; 土曜 {users_sat_p:,.0f} 人)</div>
    <div>1日平均利用者 &nbsp;&nbsp; <span class="kpi-main">{avg_total_p:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {avg_week_p:.2f} 人 &nbsp;&nbsp; 土曜 {avg_sat_p:.2f} 人)</div>
    <div>確定稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline;">{occ_week_p:.2f} %</span> &nbsp;&nbsp; 土曜 <span style="text-decoration:underline;">{occ_sat_p:.2f} %</span>)</div>
    <div style="margin-top: 5px; display: flex; align-items: flex-end; flex-wrap: wrap; gap: 15px;">
        <div>確定総売上 &nbsp;&nbsp; <span class="sales-highlight">¥{confirmed_sales:,.0f}</span></div>
        <div>確定客単価 &nbsp;&nbsp; <span class="sales-highlight">¥{unit_price:,.0f}</span></div>
        <div style="font-size: 0.9rem; color: #334155; padding-bottom: 3px; border-left: 2px solid #cbd5e1; padding-left: 15px;">
            稼働80%目安: ¥{sales_80_p:,.0f} (<span style="color:{color_80_p}; font-weight:bold;">{sign_80_p}{diff_80_p:,.0f}円</span>) &nbsp;|&nbsp; 稼働85%目安: ¥{sales_85_p:,.0f}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    daily_prev['period'] = np.where(daily_prev['サービス日付'].dt.day <= 15, '前半', '後半')
    avg_first = daily_prev[daily_prev['period']=='前半']['利用者数'].mean()
    avg_second = daily_prev[daily_prev['period']=='後半']['利用者数'].mean()
    if pd.isna(avg_first): avg_first = 0
    if pd.isna(avg_second): avg_second = 0
    
    fig1 = go.Figure(go.Scatter(x=['前半', '後半', '合計'], y=[avg_first, avg_second, avg_total_p], mode='lines+markers', line=dict(color='#3b82f6', width=3), marker=dict(size=8)))
    fig1.update_layout(title='平均人数の推移', height=200, margin=dict(l=20,r=30,t=30,b=10), yaxis=dict(range=[15, max(avg_first, avg_second, avg_total_p)+2]))
    st.plotly_chart(fig1, use_container_width=True, config={'staticPlot': True})

with col2:
    weekday_order = {0:'月', 1:'火', 2:'水', 3:'木', 4:'金', 5:'土'}
    d = daily_prev.copy()
    d['曜日名'] = d['曜日'].map(weekday_order)
    d['定員'] = d['曜日'].apply(lambda x: cap_sat if x == 5 else cap_week)
    d['稼働率'] = d['利用者数'] / d['定員'] * 100
    
    d['曜日_cat'] = pd.Categorical(d['曜日名'], categories=['月','火','水','木','金','土'], ordered=True)
    grp = d.groupby('曜日_cat', observed=False)['稼働率'].mean().reset_index().fillna(0)
    fig2 = go.Figure(go.Bar(x=grp['曜日_cat'], y=grp['稼働率'], marker_color=['#22c55e', '#64748b', '#3b82f6', '#f97316', '#eab308', '#64748b'], text=[f"{v:.1f}%" for v in grp['稼働率']], textposition='auto'))
    fig2.update_layout(title='曜日別 平均稼働率 (%)', height=200, margin=dict(l=20,r=30,t=30,b=10), yaxis=dict(range=[0, 110]))
    st.plotly_chart(fig2, use_container_width=True, config={'staticPlot': True})

if curr_data_exists:
    cap_total_c_month = cap_week_total_c + cap_sat_total_c
    
    # 営業日数から月間の総定員を出す
    days_week_c_month = sum(1 for d in range(1, last_day_c + 1) if datetime(yr_c, mo_c, d).weekday() <= 4)
    days_sat_c_month = sum(1 for d in range(1, last_day_c + 1) if datetime(yr_c, mo_c, d).weekday() == 5)
    cap_month_total_c = days_week_c_month * cap_week + days_sat_c_month * cap_sat
    
    sales_80_c = cap_month_total_c * 0.8 * unit_price
    sales_85_c = cap_month_total_c * 0.85 * unit_price
    diff_80_c = projected_sales_c - sales_80_c
    color_80_c = "#16a34a" if diff_80_c >= 0 else "#ef4444"
    sign_80_c = "+" if diff_80_c >= 0 else ""

    st.markdown(f'<div class="section-title">２．当月（会議当月）の営業経過・着地予想 &nbsp;&nbsp;&nbsp; 経過日数 {total_days_c} 日</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
        <div>現在までののべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_c:,.0f}</span> 人 &nbsp;&nbsp; / &nbsp;&nbsp; 累積稼働率 &nbsp;&nbsp; <span class="kpi-main">{occ_c_total:.2f} %</span></div>
        <div style="margin-top: 5px; display: flex; align-items: flex-end; flex-wrap: wrap; gap: 15px;">
            <div>当月の売上着地予想 &nbsp;&nbsp; <span class="sales-highlight" style="color:#ef4444;">約 ¥{projected_sales_c:,.0f}</span></div>
            <div style="font-size: 0.9rem; color: #334155; padding-bottom: 3px; border-left: 2px solid #cbd5e1; padding-left: 15px;">
                稼働80%目安: ¥{sales_80_c:,.0f} (<span style="color:{color_80_c}; font-weight:bold;">{sign_80_c}{diff_80_c:,.0f}円</span>) &nbsp;|&nbsp; 稼働85%目安: ¥{sales_85_c:,.0f}
            </div>
            <div style="font-size:0.85rem; color:#64748b; padding-bottom: 2px;">
                ※前月の確定単価（¥{unit_price:,.0f}）×当月予測人数（{projected_users_c:.0f}人）
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.text_area("分析・申し送りコメント", value="前月の単価水準を維持しつつ、今月は予想売上ペースも好調に推移している。", height=60)
else:
    st.markdown('<div class="section-title">２．分析コメント</div>', unsafe_allow_html=True)
    st.text_area("分析・申し送りコメント", value="前月は確定売上・単価ともに目標水準をクリア。後半にかけて稼働が安定した。", height=60)

# --- ここで確実に改ページ ---
st.markdown('<div style="page-break-before: always; height:0;"></div>', unsafe_allow_html=True)

# --- UI 描画（2ページ目: カレンダー） ---
_, last_day = calendar.monthrange(yr_p, mo_p)
html = f"""
<table class="page2-header-table">
    <tr><td style="font-size:1.1rem; font-weight:bold; text-align:center;">{mo_p} 月 確定日別データ</td><td colspan="2">平日稼働率: {occ_week_p:.2f}%</td><td colspan="2">土曜稼働率: {occ_sat_p:.2f}%</td></tr>
</table>
<table class="page2-table">
    <tr><th>日付</th><th>曜日</th><th>利用者数</th><th>稼働率</th></tr>
"""

df_dict = {}
for _, r in daily_prev.iterrows():
    df_dict[r['サービス日付'].day] = r['利用者数']
        
wd_str = ["月", "火", "水", "木", "金", "土", "日"]

row_count = 0
for day in range(1, last_day + 1):
    dt = datetime(yr_p, mo_p, day)
    w = dt.weekday()
    if w == 6: continue
        
    cap = cap_sat if w == 5 else cap_week
    users = df_dict.get(day, "")
    occ_str = ""
    cls_str = ""
    if users != "":
        occ = (users / cap) * 100
        occ_str = f"{occ:.2f}"
        if occ >= target_rate:
            cls_str = ' class="target-ok"'
    
    html += f"<tr><td>{mo_p}月{day}日</td><td>{wd_str[w]}</td><td>{users}</td><td{cls_str}>{occ_str}</td></tr>"
    row_count += 1

# 空行を埋めて高さを揃える
while row_count < 27:
    html += "<tr><td>&nbsp;</td><td></td><td></td><td></td></tr>"
    row_count += 1

html += "</table>"

st.markdown(f'<div class="page2-title">{facility} 前月実績（確定）</div>', unsafe_allow_html=True)
st.markdown(html, unsafe_allow_html=True)

# --- データベース保存機能 ---
st.markdown('<div class="no-print">', unsafe_allow_html=True)
st.markdown("---")
if st.button("💾 この確定データをデータベースに保存（蓄積）する", use_container_width=True):
    with st.spinner("スプレッドシートに保存中..."):
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            if os.path.exists('credentials.json'):
                creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
            else:
                creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
            client = gspread.authorize(creds)
            sheet = client.open_by_key('1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4')
            worksheet = sheet.worksheet("月次データ")
            
            now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            # 登録日時, 対象年月, 事業所名, 営業日数, のべ利用者数, 平日稼働率, 土曜稼働率, 確定総売上, 確定客単価, 機会損失額
            row_data = [
                now_str, month_str, facility, int(total_days_p), int(total_users_p), 
                round(occ_week_p, 2), round(occ_sat_p, 2), int(confirmed_sales), 
                int(unit_price), int(diff_80_p)
            ]
            worksheet.append_row(row_data, value_input_option='USER_ENTERED')
            st.success(f"✅ {month_str} の {facility} のデータをデータベースに保存しました！全社ダッシュボードに反映されます。")
        except Exception as e:
            st.error(f"保存に失敗しました。詳細: {e}")
st.markdown('</div>', unsafe_allow_html=True)

# --- 印刷機能 ---
import streamlit.components.v1 as components
components.html("""
    <div class="no-print" style="text-align: center; margin-top: 30px;">
        <button style="padding: 14px 28px; background-color: #ef4444; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
        onclick="window.parent.print();">
        🖨️ レポートをPDFに出力する
        </button>
    </div>
""", height=100)
