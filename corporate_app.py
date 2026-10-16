import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="全社・経営ダッシュボード", layout="wide")

FACILITY_CONFIG = {
    "リハビリ教室新松戸": {"week": 84, "sat": 40},
    "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
    "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
    "リハビリ教室サテライトクラス": {"week": 24, "sat": 24}
}

# --- スタイル定義 (画面およびPDF印刷用) ---
st.markdown("""
<style>
    /* 画面表示用スタイル */
    .report-title { 
        font-size: 1.85rem; 
        font-weight: bold; 
        border-bottom: 3px solid #3B82F6; 
        padding-bottom: 6px; 
        margin-bottom: 15px; 
        color: #0F172A; 
    }
    .kpi-container {
        display: flex;
        gap: 15px;
        margin-bottom: 20px;
    }
    .kpi-card { 
        flex: 1;
        background-color: #F8FAFC; 
        border: 1px solid #E2E8F0; 
        border-radius: 10px; 
        padding: 16px; 
        text-align: center; 
        box-shadow: 0 1px 3px rgba(0,0,0,0.06); 
    }
    .kpi-title { 
        font-size: 0.95rem; 
        color: #64748B; 
        font-weight: bold; 
        margin-bottom: 6px; 
    }
    .kpi-value { 
        font-size: 2.2rem; 
        font-weight: 900; 
        color: #1E293B; 
    }
    .kpi-sales {
        color: #EF4444 !important;
    }
    
    /* PDF印刷用スタイル (A4横で綺麗に1枚に収める) */
    @media print {
        @page { 
            size: A4 landscape; 
            margin: 8mm; 
        }
        body { 
            zoom: 0.72 !important; 
            -webkit-print-color-adjust: exact !important; 
            print-color-adjust: exact !important; 
        }
        [data-testid="stSidebar"], .stButton, .no-print, header, footer { 
            display: none !important; 
        }
        .block-container, [data-testid="stAppViewBlockContainer"] { 
            padding: 0 !important; 
            margin: 0 !important; 
            max-width: 100% !important; 
            width: 100% !important; 
        }
        [data-testid="stPlotlyChart"] {
            width: 100% !important;
            max-width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=30)
def get_corporate_data():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = None
        if os.path.exists("credentials.json"):
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        elif "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            
        if not creds:
            return pd.DataFrame()
            
        client = gspread.authorize(creds)
        sheet_id = '1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4'
        spreadsheet = client.open_by_key(sheet_id)
        
        # 月次実績データ（優先）または月次データを取得
        try:
            ws = spreadsheet.worksheet("月次実績データ")
        except gspread.exceptions.WorksheetNotFound:
            try:
                ws = spreadsheet.worksheet("月次データ")
            except:
                return pd.DataFrame()
                
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        # 列名ゆれの吸収
        col_rename = {
            '対象年月': '対象月',
            '事業所名': '事業所',
            'のべ利用者数': '延べ利用者数',
            '確定客単価': '利用者単価'
        }
        df.rename(columns=col_rename, inplace=True)
        return df
    except Exception as e:
        st.error(f"スプレッドシート読込エラー: {e}")
        return pd.DataFrame()

df_raw = get_corporate_data()

if df_raw.empty or '対象月' not in df_raw.columns:
    st.info("💡 スプレッドシートにデータがまだありません。「月次確定 分析ツール」で各事業所の実績を保存してください。")
    st.stop()

# 重複排除（同じ対象月に同じ事業所のデータがある場合は最新の行を採用）
sort_col = '報告日時' if '報告日時' in df_raw.columns else df_raw.columns[0]
df = df_raw.sort_values(sort_col).drop_duplicates(subset=['対象月', '事業所'], keep='last').copy()

# 型変換
for col in ['確定総売上', '延べ利用者数', '営業日数', '利用者単価', '総合稼働率', '1日平均利用_平日', '1日平均利用_土曜']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

months = sorted(df['対象月'].astype(str).unique(), reverse=True)

with st.sidebar:
    st.header("🗓️ 抽出条件")
    selected_month = st.selectbox("確認する対象月を選択", months, index=0)
    
    st.markdown("---")
    st.markdown("### 🖨️ レポート出力")
    st.caption("A4横サイズで全社会議用レポートをPDF保存できます。")
    import streamlit.components.v1 as components
    components.html("""
        <style>
            @media print { body { display: none !important; } }
        </style>
        <div class="no-print" style="text-align: center;">
            <button style="width: 100%; height: 50px; background-color: #3B82F6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.05rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
            onclick="window.parent.print();">
                🖨️ 全社レポートをPDF出力（印刷）
            </button>
        </div>
    """, height=60)

df_month = df[df['対象月'].astype(str) == selected_month].copy()

# --- 全社集計値の計算 ---
total_sales = df_month['確定総売上'].sum()
total_users = df_month['延べ利用者数'].sum()
avg_unit_price = total_sales / total_users if total_users > 0 else 0

# 全社総合稼働率の計算（各事業所の定員合計に基づく加重集計）
tot_cap = 0
for _, row in df_month.iterrows():
    fac_name = row.get('事業所', '')
    users = row.get('延べ利用者数', 0)
    occ = row.get('総合稼働率', 0)
    if occ > 0:
        tot_cap += (users / (occ / 100))
    else:
        days = row.get('営業日数', 26)
        c_week = FACILITY_CONFIG.get(fac_name, {}).get('week', 30)
        tot_cap += c_week * days

overall_occ = (total_users / tot_cap * 100) if tot_cap > 0 else 0

# --- タイトルヘッダー ---
st.markdown(f'<div class="report-title">🏢 {selected_month} 法人全体 経営会議ダッシュボード</div>', unsafe_allow_html=True)

# --- 4大KPIカード ---
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">全社 確定総売上</div>
        <div class="kpi-value kpi-sales">¥{int(total_sales):,}</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">全社 延べ利用者数</div>
        <div class="kpi-value">{int(total_users):,} <span style="font-size:1.2rem;">人</span></div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">全社 総合稼働率</div>
        <div class="kpi-value" style="color: {'#16A34A' if overall_occ >= 80 else '#EF4444'};">{overall_occ:.1f} <span style="font-size:1.2rem;">%</span></div>
    </div>
    """, unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">全社 平均客単価</div>
        <div class="kpi-value">¥{int(avg_unit_price):,}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

# --- グラフ表示（横並び2列） ---
g_col1, g_col2 = st.columns(2)

with g_col1:
    fig_sales = go.Figure(go.Bar(
        x=df_month['事業所'], 
        y=df_month['確定総売上'], 
        text=[f"¥{int(v):,}" for v in df_month['確定総売上']], 
        textposition='auto', 
        textfont=dict(size=14, color='white', weight='bold'),
        marker_color='#3B82F6'
    ))
    fig_sales.update_layout(
        title=dict(text='事業所別 確定売上（円）', font=dict(size=16)), 
        height=320, 
        margin=dict(l=10, r=10, t=35, b=10),
        yaxis=dict(title='売上（円）')
    )
    st.plotly_chart(fig_sales, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

with g_col2:
    fig_occ = go.Figure(go.Bar(
        x=df_month['事業所'], 
        y=df_month['総合稼働率'], 
        text=[f"{v:.1f}%" for v in df_month['総合稼働率']], 
        textposition='auto', 
        textfont=dict(size=14, color='white', weight='bold'),
        marker_color='#10B981'
    ))
    fig_occ.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="8割ライン", annotation_position="top right")
    fig_occ.update_layout(
        title=dict(text='事業所別 総合稼働率（%）', font=dict(size=16)), 
        height=320, 
        margin=dict(l=10, r=10, t=35, b=10), 
        yaxis=dict(range=[0, 110], ticksuffix='%')
    )
    st.plotly_chart(fig_occ, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

# --- 事業所別 内訳比較表 ---
st.markdown("### 🏢 事業所別 実績内訳一覧")

rows = []
for _, r in df_month.iterrows():
    s = r.get('確定総売上', 0)
    u = r.get('延べ利用者数', 0)
    o = r.get('総合稼働率', 0)
    up = r.get('利用者単価', 0) or (s / u if u > 0 else 0)
    sh = (s / total_sales * 100) if total_sales > 0 else 0
    
    rows.append({
        '事業所名': r.get('事業所', ''),
        '確定総売上': f"¥{int(s):,}",
        '売上シェア': f"{sh:.1f}%",
        '延べ利用人数': f"{int(u):,}人",
        '総合稼働率': f"{o:.1f}%",
        '客単価': f"¥{int(up):,}",
        '平日平均利用': f"{float(r.get('1日平均利用_平日', 0)):.1f}人",
        '土曜平均利用': f"{float(r.get('1日平均利用_土曜', 0)):.1f}人",
        '営業日数': f"{int(r.get('営業日数', 0))}日"
    })

# 全社合計行
rows.append({
    '事業所名': '【法人全体 合計/平均】',
    '確定総売上': f"¥{int(total_sales):,}",
    '売上シェア': "100.0%",
    '延べ利用人数': f"{int(total_users):,}人",
    '総合稼働率': f"{overall_occ:.1f}%",
    '客単価': f"¥{int(avg_unit_price):,}",
    '平日平均利用': f"{df_month['1日平均利用_平日'].sum():.1f}人",
    '土曜平均利用': f"{df_month['1日平均利用_土曜'].sum():.1f}人",
    '営業日数': f"{int(df_month['営業日数'].max())}日"
})

df_table = pd.DataFrame(rows)
st.dataframe(df_table, use_container_width=True, hide_index=True)

# --- 各事業所の報告コメント一覧 ---
st.markdown("---")
st.markdown(f"### 📝 {selected_month} 各事業所の報告コメント")
cols_comment = st.columns(len(df_month) if len(df_month) > 0 else 1)

for idx, (_, r) in enumerate(df_month.iterrows()):
    with st.expander(f"📌 {r.get('事業所')} の報告事項", expanded=True):
        comm_c1, comm_c2 = st.columns(2)
        with comm_c1:
            st.markdown("<div style='font-weight:bold; color:#1E293B; margin-bottom:4px;'>【営業状況コメント】</div>", unsafe_allow_html=True)
            st.info(r.get('営業状況コメント') or '（記載なし）')
        with comm_c2:
            st.markdown("<div style='font-weight:bold; color:#1E293B; margin-bottom:4px;'>【人事・車両・インシデント等】</div>", unsafe_allow_html=True)
            st.warning(r.get('人事等コメント') or '（記載なし）')
