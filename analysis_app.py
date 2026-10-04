import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import calendar
from datetime import datetime
import io

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
        "リハビリ教室サテライトクラス": {"week": 24, "sat": 24},
        "とばとらんどの松戸": {"week": 24, "sat": 24},
        "とばとらんどの新松戸": {"week": 24, "sat": 24}
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
        import datetime
        _, last_day_c = calendar.monthrange(curr_month_dt.year, curr_month_dt.month)
        total_biz_days_c = sum(1 for d in range(1, last_day_c + 1) if datetime.date(curr_month_dt.year, curr_month_dt.month, d).weekday() <= 5)
        avg_total_c = total_users_c / (days_week_c + days_sat_c) if (days_week_c + days_sat_c) > 0 else 0
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



# --- UI 描画（1ページ目） ---
st.markdown(f'<div class="report-title">{month_str} 確定分析レポート &nbsp;&nbsp;&nbsp; {facility}</div>', unsafe_allow_html=True)

st.markdown(f'<div class="section-title">１．前月の営業報告（確定値） &nbsp;&nbsp;&nbsp; 営業日数 {total_days_p} 日</div>', unsafe_allow_html=True)
st.markdown(f"""
<div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
    <div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_p:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {users_week_p:,.0f} 人 &nbsp;&nbsp; 土曜 {users_sat_p:,.0f} 人)</div>
    <div>1日平均利用者 &nbsp;&nbsp; <span class="kpi-main">{avg_total_p:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {avg_week_p:.2f} 人 &nbsp;&nbsp; 土曜 {avg_sat_p:.2f} 人)</div>
    <div>確定稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline;">{occ_week_p:.2f} %</span> &nbsp;&nbsp; 土曜 <span style="text-decoration:underline;">{occ_sat_p:.2f} %</span>)</div>
    <div style="margin-top: 5px; display: flex; align-items: flex-end;">
        <div style="margin-right: 30px;">確定総売上 &nbsp;&nbsp; <span class="sales-highlight">¥{confirmed_sales:,.0f}</span></div>
        <div style="margin-right: 30px;">確定平均客単価 &nbsp;&nbsp; <span class="sales-highlight">¥{unit_price:,.0f}</span></div>
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
    st.markdown(f'<div class="section-title">２．当月（会議当月）の営業経過・着地予想 &nbsp;&nbsp;&nbsp; 経過日数 {total_days_c} 日</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
        <div>現在までののべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_c:,.0f}</span> 人 &nbsp;&nbsp; / &nbsp;&nbsp; 累積稼働率 &nbsp;&nbsp; <span class="kpi-main">{occ_c_total:.2f} %</span></div>
        <div style="margin-top: 5px; display: flex; align-items: flex-end;">
            <div style="margin-right: 30px;">当月の売上着地予想 &nbsp;&nbsp; <span class="sales-highlight" style="color:#ef4444;">約 ¥{projected_sales_c:,.0f}</span></div>
            <div style="font-size:0.85rem; color:#64748b; padding-bottom: 2px;">
                ※前月の確定客単価（¥{unit_price:,.0f}） × 当月の着地予想人数（{projected_users_c:.0f}人）で算出
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

# --- 印刷機能 ---
import streamlit.components.v1 as components
components.html("""
    <div style="text-align: center; margin-top: 30px;">
        <button style="padding: 14px 28px; background-color: #ef4444; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
        onclick="window.parent.print();">
        🖨️ レポートをPDFに出力する
        </button>
    </div>
""", height=100)
