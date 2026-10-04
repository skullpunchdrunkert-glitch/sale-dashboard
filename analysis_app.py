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
        _, last_day_c = calendar.monthrange(curr_month_dt.year, curr_month_dt.month)
        total_biz_days_c = sum(1 for d in range(1, last_day_c + 1) if datetime(curr_month_dt.year, curr_month_dt.month, d).weekday() <= 5)
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




# --- UI 1ページ目 ---
col_header1, col_header2 = st.columns([2, 1])
with col_header1:
    st.markdown(f'<div class="report-title">{month_str} 確定実績レポート &nbsp;&nbsp;&nbsp; {facility} &nbsp;&nbsp; <span style="font-size: 1rem; font-weight: normal; color: #475569;">設定定員: 平日 {cap_week}名 / 土祝 {cap_sat}名</span></div>', unsafe_allow_html=True)
with col_header2:
    st.write("") # Spacer

st.markdown(f'<div class="section-title">1. 前月（確定）の営業報告 &nbsp;&nbsp;&nbsp; 営業日数 {total_days_p} 日</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"""
    <div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
        <div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_p:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {users_week_p:,.0f} 人 &nbsp;&nbsp; 土祝 {users_sat_p:,.0f} 人)</div>
        <div>1日平均利用 &nbsp;&nbsp; <span class="kpi-main">{avg_total_p:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {avg_week_p:.2f} 人 &nbsp;&nbsp; 土祝 {avg_sat_p:.2f} 人)</div>
        <div>稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline;">{occ_week_p:.2f} %</span> &nbsp;&nbsp; 土祝 <span style="text-decoration:underline;">{occ_sat_p:.2f} %</span>)</div>
        
        <div style="margin-top: 15px; padding-top: 10px; border-top: 1px dashed #CBD5E1;">
            <div style="font-size: 1.1rem; font-weight: bold; color: #0F172A; margin-bottom: 5px;">確定売上 &nbsp;&nbsp; <span class="kpi-main kpi-sales" style="font-size: 1.4rem;">¥{confirmed_sales:,.0f}</span></div>
            <div style="margin-left: 10px; color: #475569;">
                ・介護保険請求額: ¥{insurance_sales:,.0f}<br>
                ・自費請求額: ¥{selfpay_sales:,.0f}
            </div>
            <div style="margin-top: 10px;">確定客単価 &nbsp;&nbsp; <span class="kpi-main">¥{unit_price:,.0f}</span></div>
        </div>
    """, unsafe_allow_html=True)

    # 稼働率8割・8.5割との差額
    total_cap_p = cap_week_total_p + cap_sat_total_p
    sales_80 = total_cap_p * 0.8 * unit_price
    sales_85 = total_cap_p * 0.85 * unit_price
    diff_80 = confirmed_sales - sales_80
    diff_85 = confirmed_sales - sales_85
    
    color_80 = "red" if diff_80 < 0 else "blue"
    color_85 = "red" if diff_85 < 0 else "blue"
    sign_80 = "" if diff_80 < 0 else "+"
    sign_85 = "" if diff_85 < 0 else "+"
    
    st.markdown(f"""
        <div style="margin-top: 15px; padding: 10px; background-color: #F8FAFC; border-radius: 5px;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 0.95rem;">目標稼働率との売上差額（実績ベース）</div>
            <div style="font-size: 0.9rem;">
                稼働率 80.0% の場合: <span style="color: {color_80};">{sign_80}¥{diff_80:,.0f}</span> (目標 ¥{sales_80:,.0f})<br>
                稼働率 85.0% の場合: <span style="color: {color_85};">{sign_85}¥{diff_85:,.0f}</span> (目標 ¥{sales_85:,.0f})
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    import plotly.graph_objects as go
    if not daily_prev.empty:
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=daily_prev['サービス日付'], y=daily_prev['利用者数'], mode='lines+markers', line=dict(color='#2563EB', width=2), name='利用者数'))
        fig1.update_layout(title='日別利用者数推移（確定月）', height=180, margin=dict(l=20,r=20,t=30,b=10), yaxis=dict(range=[0, max(cap_week, cap_sat)+5]))
        st.plotly_chart(fig1, use_container_width=True, config={'staticPlot': True})
        
        # 曜日別稼働率
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
            
            fig2 = go.Figure(data=[go.Bar(x=wd_agg['wd_name'], y=wd_agg['occ'], marker_color='#10B981')])
            fig2.update_layout(title='曜日別稼働率（%）', height=180, margin=dict(l=20,r=20,t=30,b=10), yaxis=dict(range=[0, 110]))
            st.plotly_chart(fig2, use_container_width=True, config={'staticPlot': True})


if curr_data_exists:
    st.markdown(f'<div class="section-title" style="margin-top: 15px;">2. 当月（会議当月）の営業経過・着地予想 &nbsp;&nbsp;&nbsp; 経過日数 {total_days_c} 日</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
        <div>現在までののべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{total_users_c:,.0f}</span> 人 &nbsp;&nbsp; / &nbsp;&nbsp; 累積稼働率 &nbsp;&nbsp; <span class="kpi-main">{occ_c_total:.2f} %</span></div>
        <div style="margin-top: 5px; display: flex; align-items: flex-end;">
            <div>当月の売上着地予想 &nbsp;&nbsp; <span class="kpi-main kpi-sales" style="color:#EF4444;">約 ¥{projected_sales_c:,.0f}</span></div>
            <div style="font-size: 0.8rem; color:#64748B; margin-bottom:3px; margin-left: 10px;">※前月の確定客単価 (¥{unit_price:,.0f}) × 当月の着地予想人数 ({projected_users_c:,.0f}人) で算出</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
st.markdown('<div style="margin-top:20px; font-weight:bold; color:#0F172A; border-bottom:1px solid #CBD5E1; margin-bottom:10px;">分析・申し送りコメント</div>', unsafe_allow_html=True)
st.text_area("", placeholder="こちらに会議用のコメントや共有事項を入力してください...", height=80, label_visibility="collapsed")

# --- UI 2ページ目 ---
st.markdown('<div style="page-break-before: always; height:0;"></div>', unsafe_allow_html=True)

# 確定月と当月の日々実績データの左右対比
st.markdown(f'<div class="page2-title">{facility} 日々実績データ（確定月・当月比較）</div>', unsafe_allow_html=True)

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
<table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 0.85rem; margin-bottom: 20px;">
    <tr style="background-color: #F1F5F9; border: 1px solid #CBD5E1;">
        <th colspan="4" style="padding: 5px; border: 1px solid #CBD5E1;">【確定月】{mo_p}月</th>
        <th colspan="4" style="padding: 5px; border: 1px solid #CBD5E1; background-color: #F0FDF4;">【当月】{curr_month_dt.month if curr_data_exists else '-'}月</th>
    </tr>
    <tr style="background-color: #F8FAFC; border: 1px solid #CBD5E1;">
        <th style="border: 1px solid #CBD5E1; width: 8%;">日付</th>
        <th style="border: 1px solid #CBD5E1; width: 7%;">曜日</th>
        <th style="border: 1px solid #CBD5E1; width: 10%;">利用者数</th>
        <th style="border: 1px solid #CBD5E1; width: 15%;">稼働率</th>
        <th style="border: 1px solid #CBD5E1; width: 8%; background-color: #F0FDF4;">日付</th>
        <th style="border: 1px solid #CBD5E1; width: 7%; background-color: #F0FDF4;">曜日</th>
        <th style="border: 1px solid #CBD5E1; width: 10%; background-color: #F0FDF4;">利用者数</th>
        <th style="border: 1px solid #CBD5E1; width: 15%; background-color: #F0FDF4;">稼働率</th>
    </tr>
"""

import calendar
import datetime
_, last_day_p = calendar.monthrange(yr_p, mo_p)
if curr_data_exists:
    _, last_day_c = calendar.monthrange(curr_month_dt.year, curr_month_dt.month)
else:
    last_day_c = 0

max_days = max(last_day_p, last_day_c)

row_count = 0
for day in range(1, max_days + 1):
    # 確定月
    p_date_html = ""
    p_wd_html = ""
    p_users_html = ""
    p_occ_html = ""
    
    if day <= last_day_p:
        dt_p = datetime.date(yr_p, mo_p, day)
        w_p = dt_p.weekday()
        if w_p != 6: # exclude Sunday
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
            row_count += 1
            
    # 当月
    c_date_html = ""
    c_wd_html = ""
    c_users_html = ""
    c_occ_html = ""
    
    if curr_data_exists and day <= last_day_c:
        dt_c = datetime.date(curr_month_dt.year, curr_month_dt.month, day)
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
            row_count = max(row_count, day) # Just to ensure we count rows
            
    # Print row if at least one side is not Sunday
    if p_date_html != "" or c_date_html != "":
        html_table += f"<tr><td style='border: 1px solid #CBD5E1;'>{p_date_html}</td><td style='border: 1px solid #CBD5E1;'>{p_wd_html}</td><td style='border: 1px solid #CBD5E1;'>{p_users_html}</td><td style='border: 1px solid #CBD5E1;'>{p_occ_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC;'>{c_date_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC;'>{c_wd_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC;'>{c_users_html}</td><td style='border: 1px solid #CBD5E1; background-color: #F8FAFC;'>{c_occ_html}</td></tr>"

html_table += "</table>"
st.markdown(html_table, unsafe_allow_html=True)


# --- 曜日別稼働率の比較表 ---
if curr_data_exists:
    st.markdown('<div style="font-size:1.1rem; font-weight:bold; margin-top:20px; color:#1E293B;">確定月と当月の「曜日別稼働率」比較表</div>', unsafe_allow_html=True)
    
    # Calculate for current month
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
    <table style="width: 100%; border-collapse: collapse; text-align: center; font-size: 0.9rem; margin-bottom: 20px;">
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
    
    comp_html += "<tr><td style='border: 1px solid #CBD5E1; font-weight:bold; background-color: #F8FAFC;'>【確定月】</td>"
    for w in range(6):
        occ = wd_dict_p.get(w, 0)
        cls_str = ' style="border: 1px solid #CBD5E1; font-weight:bold; color: #EF4444; background-color: #FEE2E2;"' if occ >= 80 else ' style="border: 1px solid #CBD5E1;"'
        comp_html += f"<td{cls_str}>{occ:.1f}%</td>"
    comp_html += "</tr>"
    
    comp_html += "<tr><td style='border: 1px solid #CBD5E1; font-weight:bold; background-color: #F0FDF4;'>【当月予測】</td>"
    for w in range(6):
        occ = wd_dict_c.get(w, 0)
        cls_str = ' style="border: 1px solid #CBD5E1; font-weight:bold; color: #EF4444; background-color: #FEE2E2;"' if occ >= 80 else ' style="border: 1px solid #CBD5E1;"'
        comp_html += f"<td{cls_str}>{occ:.1f}%</td>"
    comp_html += "</tr></table>"
    
    st.markdown(comp_html, unsafe_allow_html=True)


# --- 印刷ボタン ---
import streamlit.components.v1 as components
components.html("""
    <div style="text-align: center; margin-top: 30px;">
        <button style="padding: 14px 28px; background-color: #3B82F6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
        onclick="window.parent.print();">
            🖨️ PDFに出力する（印刷）
        </button>
        <p style="font-size: 0.85rem; color: #64748B; margin-top: 10px;">
            ※ Chrome等のブラウザの印刷機能を使用します。<br>
            ※ 「送信先」を「PDFに保存」に設定し、レイアウトを「縦」にして保存してください。<br>
            ※ 「背景のグラフィック」にチェックを入れると色が綺麗に印刷されます。
        </p>
    </div>
""", height=200)
