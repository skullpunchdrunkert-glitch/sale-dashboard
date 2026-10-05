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

FACILITY_CONFIG = {
    "リハビリ教室新松戸": {"week": 84, "sat": 40},
    "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
    "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
    "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
}
selected_facility = st.sidebar.selectbox("対象事業所選択", list(FACILITY_CONFIG.keys()), index=2)
cap_week = FACILITY_CONFIG[selected_facility]["week"]
cap_sat = FACILITY_CONFIG[selected_facility]["sat"]
facility = selected_facility

if mode == "📊 過去データ閲覧":
    st.markdown('<div class="report-title">📊 過去データ（実績表）</div>', unsafe_allow_html=True)
    st.markdown("Googleスプレッドシート（月次実績データ）に保存された過去の確定実績を一覧表で振り返ります。")
    


    try:
        import gspread
        from google.oauth2.service_account import Credentials
        import os
        import pandas as pd
        
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
            
            try:
                ws = spreadsheet.worksheet("月次実績データ")
                records = ws.get_all_records()
                if not records:
                    st.info("データがまだありません。各月の実績を保存してください。")
                    st.stop()
                    
                df_history = pd.DataFrame(records)
                df_fac = df_history[df_history['事業所'] == selected_facility].copy()
                
                if df_fac.empty:
                    st.info(f"{selected_facility} の過去データはまだ保存されていません。")
                    st.stop()
                
                # Sort chronologically by 対象月, newest first
                df_fac['対象月_str'] = df_fac['対象月'].astype(str)
                df_fac = df_fac.sort_values('対象月_str', ascending=False)
                
                # Create display dataframe
                df_display = df_fac[['対象月_str', '営業日数', '延べ利用者数', '1日平均利用_平日', '1日平均利用_土曜', '総合稼働率', '要介護・支援割合', '確定総売上', '利用者単価']].copy()
                
                # Format columns
                def format_yen(x):
                    try: return f"¥{int(x):,}"
                    except: return x
                    
                def format_pct(x):
                    try: return f"{float(x):.1f}%"
                    except: return x
                    
                df_display['確定総売上'] = df_display['確定総売上'].apply(format_yen)
                df_display['利用者単価'] = df_display['利用者単価'].apply(format_yen)
                df_display['総合稼働率'] = df_display['総合稼働率'].apply(format_pct)
                df_display.rename(columns={'対象月_str': '対象月'}, inplace=True)
                
                st.markdown("### 📈 実績一覧表")
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                st.markdown("---")
                st.markdown("### 📝 過去の営業状況コメント履歴")
                
                for _, r in df_fac.iterrows(): 
                    with st.expander(f"{r['対象月_str']} のレポート (報告日: {str(r.get('報告日時',''))[:10]})"):
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            st.markdown("**【営業状況コメント】**")
                            st.info(r.get('営業状況コメント', '記載なし'))
                        with cc2:
                            st.markdown("**【人事・車両・インシデント等】**")
                            st.warning(r.get('人事等コメント', '記載なし'))
            except gspread.exceptions.WorksheetNotFound:
                st.info("過去データ（月次実績データ）がまだ存在しません。先にデータ保存を行ってください。")
        else:
            st.error("認証情報が見つかりません。")
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        
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
            
            bar_colors = ['#F97316' if val >= 80 else '#10B981' for val in wd_agg['occ']]
            fig2 = go.Figure(data=[go.Bar(
                x=wd_agg['wd_name'], 
                y=wd_agg['occ'], 
                marker_color=bar_colors,
                text=[f'{val:.1f}%' for val in wd_agg['occ']],
                textposition='inside',
                insidetextanchor='start',
                textfont=dict(size=15, color='white', weight='bold')
            )])
            fig2.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="8割ライン", annotation_position="top right")
            fig2.update_layout(title=dict(text='曜日別稼働率（%）', font=dict(size=16)), height=250, margin=dict(l=5,r=5,t=25,b=10), yaxis=dict(range=[0, 110]))
            fig2.update_layout(width=420)
        st.plotly_chart(fig2, use_container_width=False, config={'displayModeBar': False})


if curr_data_exists:
    st.markdown(f'<div class="section-title" style="margin-top: 10px; font-size: 1.25rem !important;">2. 当月（会議当月）の営業経過・着地予想 <span style="font-size: 1.05rem; font-weight: normal; margin-left: 15px;">当月営業 {total_biz_days_c}日 (平日 {total_biz_week_c}日 土曜 {total_biz_sat_c}日) &nbsp;/&nbsp; 経過 {total_days_c}日 (平日 {days_week_c}日 土曜 {days_sat_c}日)</span></div>', unsafe_allow_html=True)
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
                
                ws_name = "月次実績データ"
                try:
                    ws = spreadsheet.worksheet(ws_name)
                except gspread.exceptions.WorksheetNotFound:
                    ws = spreadsheet.add_worksheet(title=ws_name, rows="1000", cols="20")
                    headers = ['報告日時', '対象月', '事業所', '営業日数', '延べ利用者数', '1日平均利用_平日', '1日平均利用_土曜', '要介護・支援割合', '確定総売上', '利用者単価', '総合稼働率', '平日稼働率', '土曜稼働率', '営業状況コメント', '人事等コメント']
                    ws.append_row(headers)
                
                records = ws.get_all_records()
                
                row_to_update = None
                for i, record in enumerate(records):
                    if str(record.get('対象月', '')) == str(month_str) and str(record.get('事業所', '')) == str(facility):
                        row_to_update = i + 2
                        break
                        
                from datetime import datetime as dt_now
                now_str = dt_now.now().strftime("%Y-%m-%d %H:%M:%S")
                
                ratio_str_val = ratio_str if 'ratio_str' in locals() else "データなし"
                overall_occ_val = (occ_week_p*days_week_p + occ_sat_p*days_sat_p)/total_days_p if total_days_p>0 else 0
                
                new_row = [
                    now_str,
                    month_str,
                    facility,
                    int(total_days_p),
                    int(total_users_p),
                    round(avg_week_p, 2),
                    round(avg_sat_p, 2),
                    ratio_str_val,
                    int(confirmed_sales),
                    int(unit_price),
                    round(overall_occ_val, 2),
                    round(occ_week_p, 2),
                    round(occ_sat_p, 2),
                    comment_text,
                    incident_comment
                ]
                
                # Excel column O is the 15th letter
                if row_to_update:
                    ws.update(f"A{row_to_update}:O{row_to_update}", [new_row])
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
