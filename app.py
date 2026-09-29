import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import streamlit.components.v1 as components
import calendar
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="管理者会議資料", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* 基本のスタイル */
    .report-title { font-size: 1.6rem; font-weight: bold; border-bottom: 2px solid #2dce89; padding-bottom: 3px; margin-bottom: 5px; color: #1f2937; }
    .section-title { font-size: 1.15rem; font-weight: bold; background-color: #e2e8f0; padding: 2px 10px; border-left: 5px solid #475569; margin-top: 4px; margin-bottom: 2px; color: #1e293b; }
    .kpi-main { font-size: 1.15rem; font-weight: bold; color: #0f172a; }
    .sales-highlight { font-size: 1.35rem; font-weight: bold; color: #0f172a; border-bottom: 2px solid #2dce89; padding-bottom: 2px; }
    
    .page2-title { font-size: 1.6rem; font-weight: bold; text-align: left; }
    .page2-header-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; margin-bottom: 2px; }
    .page2-header-table td { padding: 4px 10px; text-align: center; }
    
    /* 表の縦枠の高さ */
    .page2-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; margin-bottom: 10px; }
    .page2-table th, .page2-table td { border: 1px solid #111; padding: 2px; text-align: center; height: 28px; }
    .page2-table th { background-color: #f8fafc; font-weight: 600; }
    .target-ok { background-color: #bbf7d0 !important; font-weight: bold; }
    
    .summary-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 5px; }
    .summary-table th, .summary-table td { border: 1px solid #111; padding: 4px; text-align: center; }

    /* 高画質PDF出力のための設定 */
    @media print {
        @page { size: A4 portrait; margin: 0; }
        body { zoom: 0.85 !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        header, .stSidebar, .stToolbar, footer { display: none !important; }
        .element-container:has(iframe) { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
        iframe { display: none !important; }
        .block-container { padding: 12mm 10mm !important; margin: 0 !important; max-width: 100% !important; width: 100% !important; }
        .stApp { padding-bottom: 0 !important; margin-bottom: 0 !important; }
        .element-container { margin-bottom: 0 !important; padding-bottom: 0 !important; }
        .stMarkdown { margin-bottom: 0 !important; }
        .page-break { page-break-before: always !important; break-before: page !important; height: 0 !important; margin: 0 !important; padding: 0 !important; border: none !important; display: block; }
        textarea { border: 1px solid #ccc !important; resize: none !important; overflow: hidden !important; }
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def load_data():
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    if os.path.exists('credentials.json'):
        credentials = Credentials.from_service_account_file('credentials.json', scopes=scopes)
    else:
        credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
        
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key('1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4').get_worksheet_by_id(1338228675)
    records = worksheet.get_all_records()
    return pd.DataFrame(records)

with st.sidebar:
    st.header("⚙️ 帳票設定")
    
    try:
        df = load_data()
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        st.stop()
        
    # 列名の空白などを削除して正規化（安全対策）
    df.columns = df.columns.str.strip()
    df['営業日'] = pd.to_datetime(df['営業日'])
    df['年月'] = df['営業日'].dt.strftime('%Y年%m月')

    
    FACILITY_CONFIG = {
        "リハビリ教室新松戸": {"week": 84, "sat": 40},
        "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
        "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
        "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
    }
    facility_list = list(FACILITY_CONFIG.keys())
    for f in df['事業所名'].unique():
        if f not in facility_list:
            facility_list.append(f)
            FACILITY_CONFIG[f] = {"week": 30, "sat": 30}

    facility = st.selectbox("事業所名", facility_list, index=facility_list.index("ことばとからだのリハビリ教室") if "ことばとからだのリハビリ教室" in facility_list else 0)
    
    months = sorted(df['年月'].unique())
    prev_month_str = st.selectbox("前月 (実績)", options=months, index=0 if len(months)>0 else 0)
    curr_month_str = st.selectbox("当月 (予想)", options=months, index=1 if len(months)>1 else 0)
    
    st.markdown("---")
    confirmed_sales = st.number_input(f"{prev_month_str} の確定総売上 (円)", value=6293656, step=10000)
    
    default_week = FACILITY_CONFIG[facility]["week"]
    default_sat = FACILITY_CONFIG[facility]["sat"]
    cap_week = st.number_input("平日定員 (人)", value=default_week, step=1)
    cap_sat = st.number_input("土曜定員 (人)", value=default_sat, step=1)
    target_rate = st.slider("目標稼働率 (%)", 60, 100, 80, 5)

# Data Processing
cols_to_sum = [c for c in df.columns if '人数' in c]
for col in cols_to_sum:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

df['合計'] = df[cols_to_sum].sum(axis=1)

kaigo_cols = [c for c in df.columns if '要介護' in c]
shien_cols = [c for c in df.columns if '支援' in c]
df['要介護_合計'] = df[kaigo_cols].sum(axis=1)
df['要支援_合計'] = df[shien_cols].sum(axis=1)

df['タイムスタンプ'] = pd.to_datetime(df['タイムスタンプ'])
df = df.sort_values('タイムスタンプ').groupby(['事業所名', '営業日']).tail(1).reset_index(drop=True)

df_fac = df[df['事業所名'] == facility].copy()
df_prev = df_fac[df_fac['年月'] == prev_month_str].copy()
df_curr = df_fac[df_fac['年月'] == curr_month_str].copy()

def calc_kpi(d):
    if d.empty: return None
    d = d.copy()
    d['曜日'] = d['営業日'].dt.dayofweek
    d['区分'] = d['曜日'].apply(lambda x: '土曜' if x == 5 else '平日')
    
    total_users = d['合計'].sum()
    days_week = len(d[d['区分'] == '平日'])
    days_sat = len(d[d['区分'] == '土曜'])
    total_days = len(d)
    
    users_week = d[d['区分'] == '平日']['合計'].sum()
    users_sat = d[d['区分'] == '土曜']['合計'].sum()
    
    avg_total = total_users / total_days if total_days > 0 else 0
    avg_week = users_week / days_week if days_week > 0 else 0
    avg_sat = users_sat / days_sat if days_sat > 0 else 0
    
    cap_week_total = days_week * cap_week
    cap_sat_total = days_sat * cap_sat
    
    occ_week = (users_week / cap_week_total * 100) if cap_week_total > 0 else 0
    occ_sat = (users_sat / cap_sat_total * 100) if cap_sat_total > 0 else 0
    
    total_kaigo = d['要介護_合計'].sum()
    total_shien = d['要支援_合計'].sum()
    ratio_kaigo = (total_kaigo / total_users * 100) if total_users > 0 else 0
    ratio_shien = (total_shien / total_users * 100) if total_users > 0 else 0
    
    return {
        'total_days': total_days, 'days_week': days_week, 'days_sat': days_sat,
        'total_users': total_users, 'users_week': users_week, 'users_sat': users_sat,
        'avg_total': avg_total, 'avg_week': avg_week, 'avg_sat': avg_sat,
        'occ_week': occ_week, 'occ_sat': occ_sat, 
        'ratio_kaigo': ratio_kaigo, 'ratio_shien': ratio_shien, 'df': d
    }

kpi_p = calc_kpi(df_prev)
kpi_c = calc_kpi(df_curr)

if not kpi_p:
    st.error("前月のデータがありません。")
    st.stop()

unit_price = confirmed_sales / kpi_p['total_users'] if kpi_p['total_users'] > 0 else 0

# --- PAGE 1 UI ---
st.markdown(f'<div class="report-title">{curr_month_str} 管理者会議資料 &nbsp;&nbsp;&nbsp; {facility}</div>', unsafe_allow_html=True)

st.markdown(f'<div class="section-title">１．前月の営業報告 &nbsp;&nbsp;&nbsp; 営業日数 {kpi_p["total_days"]} 日 &nbsp;&nbsp; (平日 {kpi_p["days_week"]} 日 &nbsp;&nbsp; 土曜 {kpi_p["days_sat"]} 日)</div>', unsafe_allow_html=True)

st.markdown(f"""
<div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
    <div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{kpi_p['total_users']:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {kpi_p['users_week']:,.0f} 人 &nbsp;&nbsp; 土曜 {kpi_p['users_sat']:,.0f} 人)</div>
    <div>1日平均利用者 &nbsp;&nbsp; <span class="kpi-main">{kpi_p['avg_total']:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {kpi_p['avg_week']:.2f} 人 &nbsp;&nbsp; 土曜 {kpi_p['avg_sat']:.2f} 人)</div>
    <div>稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline;">{kpi_p['occ_week']:.2f} %</span> &nbsp;&nbsp; 土曜 <span style="text-decoration:underline;">{kpi_p['occ_sat']:.2f} %</span>)</div>
    <div style="margin-top: 5px; display: flex; align-items: flex-end;">
        <div style="margin-right: 30px;">総売上げ &nbsp;&nbsp; <span class="sales-highlight">¥{confirmed_sales:,.0f}</span></div>
        <div style="margin-right: 30px;">単価 &nbsp;&nbsp; <span class="sales-highlight">¥{unit_price:,.0f}</span></div>
        <div style="font-size:1.05rem; color:#475569; padding-bottom: 2px;">
            介護 <span style="font-weight:bold; color:#0f172a;">{kpi_p['ratio_kaigo']:.1f}%</span> &nbsp;&nbsp;
            支援 <span style="font-weight:bold; color:#0f172a;">{kpi_p['ratio_shien']:.1f}%</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    d = kpi_p['df'].copy()
    d['period'] = np.where(d['営業日'].dt.day <= 15, '前半', '後半')
    avg_first = d[d['period']=='前半']['合計'].mean()
    avg_second = d[d['period']=='後半']['合計'].mean()
    fig1 = go.Figure(go.Scatter(x=['前半', '後半', '合計'], y=[avg_first, avg_second, kpi_p['avg_total']], mode='lines+markers', line=dict(color='#3b82f6', width=3), marker=dict(size=8)))
    # 土曜日が見切れないように r=30 に拡大
    fig1.update_layout(title='平均の推移', height=180, margin=dict(l=20,r=30,t=30,b=10), yaxis=dict(range=[15, max(avg_first, avg_second, kpi_p['avg_total'])+2]))
    st.plotly_chart(fig1, use_container_width=True, config={'staticPlot': True})
with col2:
    weekday_order = {0:'月', 1:'火', 2:'水', 3:'木', 4:'金', 5:'土'}
    d['曜日名'] = d['曜日'].map(weekday_order)
    d['定員'] = d['曜日'].apply(lambda x: cap_sat if x == 5 else cap_week)
    d['稼働率'] = d['合計'] / d['定員'] * 100
    
    d['曜日_cat'] = pd.Categorical(d['曜日名'], categories=['月','火','水','木','金','土'], ordered=True)
    grp = d.groupby('曜日_cat', observed=False)['稼働率'].mean().reset_index()
    fig2 = go.Figure(go.Bar(x=grp['曜日_cat'], y=grp['稼働率'], marker_color=['#22c55e', '#64748b', '#3b82f6', '#f97316', '#eab308', '#64748b'], text=[f"{v:.1f}%" for v in grp['稼働率']], textposition='auto'))
    # 土曜日が見切れないように r=30 に拡大
    fig2.update_layout(title='曜日別 平均稼働率 (%)', height=180, margin=dict(l=20,r=30,t=30,b=10), yaxis=dict(range=[0, 110]))
    st.plotly_chart(fig2, use_container_width=True, config={'staticPlot': True})

st.text_area("コメント (前月)", value="平日、土曜日に稼働率は8割を維持できているが、引き続き新規利用を順次進めている。", height=55, key="c1")

total_biz_days = 26 
if kpi_c:
    st.markdown(f'<div class="section-title">２．今月の営業予定 &nbsp;&nbsp;&nbsp; 月間予定営業日数 {total_biz_days} 日</div>', unsafe_allow_html=True)
    expected_sales = (kpi_c['avg_total'] * total_biz_days) * unit_price
    st.markdown(f"""
    <div style="margin-left:20px; line-height: 1.6; font-size: 0.95rem;">
        <div>管理者会議までの営業日数 &nbsp;&nbsp; {kpi_c['total_days']} 日 &nbsp;&nbsp; (平日 {kpi_c['days_week']} 日 &nbsp;&nbsp; 土曜 {kpi_c['days_sat']} 日)</div>
        <div>のべ利用者数 &nbsp;&nbsp; <span class="kpi-main">{kpi_c['total_users']:,.0f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {kpi_c['users_week']:,.0f} 人 &nbsp;&nbsp; 土曜 {kpi_c['users_sat']:,.0f} 人)</div>
        <div>1日平均利用者 &nbsp;&nbsp; <span class="kpi-main">{kpi_c['avg_total']:.2f}</span> 人 &nbsp;&nbsp;&nbsp; (平日 {kpi_c['avg_week']:.2f} 人 &nbsp;&nbsp; 土曜 {kpi_c['avg_sat']:.2f} 人)</div>
        <div>稼働率 &nbsp;&nbsp; (平日 <span style="text-decoration:underline;">{kpi_c['occ_week']:.2f} %</span> &nbsp;&nbsp; 土曜 <span style="text-decoration:underline;">{kpi_c['occ_sat']:.2f} %</span>)</div>
        <div style="margin-top: 5px; display: flex; align-items: flex-end;">
            <div style="margin-right: 30px;">売上見込（着地予想） &nbsp;&nbsp; <span class="sales-highlight">¥{expected_sales:,.0f}</span></div>
            <div style="font-size:1.05rem; color:#475569; padding-bottom: 2px;">
                介護 <span style="font-weight:bold; color:#0f172a;">{kpi_c['ratio_kaigo']:.1f}%</span> &nbsp;&nbsp;
                支援 <span style="font-weight:bold; color:#0f172a;">{kpi_c['ratio_shien']:.1f}%</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.text_area("コメント (今月)", value="前半は前月同様の稼働だが、徐々に改善してきている。", height=55, key="c2")

st.markdown('<div class="section-title">３．人事関連報告</div>', unsafe_allow_html=True)
st.text_area("人事関連", label_visibility="collapsed", height=55, key="c3")

st.markdown('<div class="section-title">４．インシデント・車両報告</div>', unsafe_allow_html=True)
st.text_area("インシデント", label_visibility="collapsed", height=55, key="c4")

st.markdown('<div class="section-title">５．その他　報告したい事項</div>', unsafe_allow_html=True)
st.text_area("その他", label_visibility="collapsed", height=55, key="c5", value="10月2日16時45分から請求関連の質問会")

# --- ここで確実に改ページ ---
st.markdown('<div class="page-break"></div>', unsafe_allow_html=True)

# --- PAGE 2 UI ---
def build_month_table(month_str, df_month, kpi):
    yr, mo = int(month_str[:4]), int(month_str[5:7])
    _, last_day = calendar.monthrange(yr, mo)
    
    html = f"""
    <table class="page2-header-table">
        <tr><td style="font-size:1.1rem; font-weight:bold; text-align:center;">{mo} 月</td><td colspan="2">平日日数: {kpi['days_week']}日</td><td colspan="2">土曜日数: {kpi['days_sat']}日</td></tr>
    </table>
    <table class="page2-table">
        <tr><th>日付</th><th>曜日</th><th>利用者数</th><th>稼働率</th></tr>
    """
    
    df_dict = {}
    if not df_month.empty:
        df_month['day'] = df_month['営業日'].dt.day
        for _, r in df_month.iterrows():
            df_dict[r['day']] = r['合計']
            
    wd_str = ["月", "火", "水", "木", "金", "土", "日"]
    
    row_count = 0
    for d in range(1, last_day + 1):
        dt = datetime(yr, mo, d)
        w = dt.weekday()
        if w == 6: continue
            
        cap = cap_sat if w == 5 else cap_week
        users = df_dict.get(d, "")
        occ_str = ""
        cls_str = ""
        if users != "":
            occ = (users / cap) * 100
            occ_str = f"{occ:.2f}"
            if occ >= target_rate:
                cls_str = ' class="target-ok"'
        
        html += f"<tr><td>{mo}月{d}日</td><td>{wd_str[w]}</td><td>{users}</td><td{cls_str}>{occ_str}</td></tr>"
        row_count += 1
        
    while row_count < 27:
        html += "<tr><td>&nbsp;</td><td></td><td></td><td></td></tr>"
        row_count += 1
        
    html += "</table>"
    
    html += f"""
    <div style="display:flex; justify-content:space-around; font-weight:bold; font-size:0.9rem; margin-top:10px;">
        <div>平日平均稼働率: {kpi['occ_week']:.2f}%</div>
        <div>土曜平均稼働率: {kpi['occ_sat']:.2f}%</div>
    </div>
    """
    
    if not df_month.empty:
        df_month['定員'] = df_month['営業日'].dt.dayofweek.apply(lambda x: cap_sat if x == 5 else cap_week)
        df_month['稼働率'] = df_month['合計'] / df_month['定員'] * 100
        grp = df_month.groupby(df_month['営業日'].dt.dayofweek).agg({'合計':['count','mean'], '稼働率':'mean'})
        
        html += """<table class="summary-table" style="margin-top:10px;">
            <tr><th>曜日</th><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th></tr>
            <tr><td>日数</td>"""
        for i in range(6):
            cnt = grp.loc[i, ('合計','count')] if i in grp.index else 0
            html += f"<td>{cnt}</td>"
        html += "</tr><tr><td>平均</td>"
        for i in range(6):
            avg = grp.loc[i, ('合計','mean')] if i in grp.index else 0
            html += f"<td>{avg:.1f}</td>"
        html += "</tr><tr><td>稼働率</td>"
        for i in range(6):
            occ = grp.loc[i, ('稼働率','mean')] if i in grp.index else 0
            cls = ' class="target-ok"' if occ >= target_rate else ''
            html += f"<td{cls}>{occ:.1f}%</td>"
        html += "</tr></table>"
        
    return html

colA, colB = st.columns([1,1])
with colA:
    st.markdown(f'<div class="page2-title">{facility}</div>', unsafe_allow_html=True)
with colB:
    st.markdown(f"""
    <table class="page2-header-table" style="float:right; width:70%;">
        <tr><td>定員</td><td>平日 {cap_week}人</td><td>土曜 {cap_sat}人</td></tr>
        <tr><td>目標</td><td>平日 {cap_week * target_rate/100:.1f}人</td><td>土曜 {cap_sat * target_rate/100:.1f}人</td></tr>
    </table>
    """, unsafe_allow_html=True)

colA, colB = st.columns(2)
with colA:
    if kpi_p: st.markdown(build_month_table(prev_month_str, df_prev, kpi_p), unsafe_allow_html=True)
with colB:
    if kpi_c: st.markdown(build_month_table(curr_month_str, df_curr, kpi_c), unsafe_allow_html=True)

# --- 印刷機能 ---
components.html("""
    <div style="text-align: center; margin-top: 30px;">
        <button style="padding: 14px 28px; background-color: #ef4444; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
        onclick="window.parent.print();">
        🖨️ PDFを出力する（高画質・ズレ防止版）
        </button>
        <p style="margin-top: 10px; font-size: 0.9rem; color: #475569; font-weight: bold;">
        ※ボタンを押すと印刷画面が開きます。プリンタの「送信先」を「PDFに保存」にして保存してください。<br>
        </p>
    </div>
""", height=120)
