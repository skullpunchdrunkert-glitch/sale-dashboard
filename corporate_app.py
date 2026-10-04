import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="全社・経営ダッシュボード", layout="wide")

st.markdown("""
<style>
    .report-title { font-size: 1.6rem; font-weight: bold; border-bottom: 2px solid #3b82f6; padding-bottom: 3px; margin-bottom: 15px; color: #1f2937; }
    .kpi-box { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .kpi-title { font-size: 0.9rem; color: #64748b; font-weight: bold; margin-bottom: 5px; }
    .kpi-value { font-size: 1.8rem; font-weight: bold; color: #0f172a; }
    .kpi-sub { font-size: 0.85rem; color: #ef4444; font-weight: bold; }
    @media print {
        .no-print { display: none !important; }
        @page { size: A4 landscape; margin: 10mm; }
        body { zoom: 0.85 !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        header, .stSidebar, .stToolbar, footer { display: none !important; }
        .element-container:has(iframe) { display: none !important; height: 0 !important; margin: 0 !important; padding: 0 !important; }
        iframe { display: none !important; }
        .block-container { padding: 5mm !important; margin: 0 !important; max-width: 100% !important; width: 100% !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🏢 法人全体・経営会議用 ダッシュボード")

@st.cache_data(ttl=60)
def get_corporate_data():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        if os.path.exists('credentials.json'):
            creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        else:
            creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key('1evcMFBhUGApDjrPgiSSjkah_W0KHnb-XK9gW4v9NYx4')
        worksheet = sheet.worksheet("月次データ")
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception as e:
        return pd.DataFrame()

df = get_corporate_data()

if df.empty or '対象年月' not in df.columns:
    st.info("まだデータベースにデータがありません。「月次確定 分析ツール」から各事業所のデータを保存してください。")
    st.stop()

# 重複排除（同じ月に同じ事業所を何度も保存した場合、一番新しい行を採用する）
df = df.sort_values('登録日時').drop_duplicates(subset=['対象年月', '事業所名'], keep='last')

# サイドバーで月を選択
months = sorted(df['対象年月'].unique(), reverse=True)
st.sidebar.header("🗓️ 抽出条件")
selected_month = st.sidebar.selectbox("表示する月を選択", months)

df_month = df[df['対象年月'] == selected_month].copy()

# データクレンジング（文字列表記対策）
for col in ['確定総売上', 'のべ利用者数', '機会損失額', '平日稼働率', '土曜稼働率']:
    df_month[col] = pd.to_numeric(df_month[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

# --- KPI計算 ---
total_sales = df_month['確定総売上'].sum()
total_users = df_month['のべ利用者数'].sum()
total_loss = df_month['機会損失額'].sum()
avg_unit_price = total_sales / total_users if total_users > 0 else 0

st.markdown(f'<div class="report-title">{selected_month} 法人全体 業績サマリー</div>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-title">全社 確定総売上</div><div class="kpi-value">¥{total_sales:,.0f}</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-title">全社 のべ利用者数</div><div class="kpi-value">{total_users:,.0f} 人</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-title">全社 平均客単価</div><div class="kpi-value">¥{avg_unit_price:,.0f}</div></div>', unsafe_allow_html=True)
with col4:
    sign = "+" if total_loss >= 0 else ""
    color = "#16a34a" if total_loss >= 0 else "#ef4444"
    st.markdown(f'<div class="kpi-box"><div class="kpi-title">全社 機会損失額 (80%基準)</div><div class="kpi-value" style="color:{color};">{sign}{total_loss:,.0f} 円</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- グラフ表示 ---
colA, colB = st.columns(2)
with colA:
    fig_sales = go.Figure(go.Bar(
        x=df_month['事業所名'], 
        y=df_month['確定総売上'], 
        text=[f"¥{v:,.0f}" for v in df_month['確定総売上']], 
        textposition='auto', 
        marker_color='#3b82f6'
    ))
    fig_sales.update_layout(title='事業所別 確定売上', height=300, margin=dict(l=20,r=20,t=40,b=20))
    st.plotly_chart(fig_sales, use_container_width=True, config={'staticPlot': True})

with colB:
    fig_occ = go.Figure()
    fig_occ.add_trace(go.Bar(
        x=df_month['事業所名'], y=df_month['平日稼働率'], name='平日稼働率', 
        text=[f"{v:.1f}%" for v in df_month['平日稼働率']], textposition='auto', marker_color='#22c55e'
    ))
    fig_occ.add_trace(go.Bar(
        x=df_month['事業所名'], y=df_month['土曜稼働率'], name='土曜稼働率', 
        text=[f"{v:.1f}%" for v in df_month['土曜稼働率']], textposition='auto', marker_color='#f97316'
    ))
    fig_occ.update_layout(title='事業所別 稼働率比較', barmode='group', height=300, margin=dict(l=20,r=20,t=40,b=20), yaxis=dict(range=[0, 110]))
    st.plotly_chart(fig_occ, use_container_width=True, config={'staticPlot': True})

# --- 詳細データテーブル ---
st.markdown("### 📄 事業所別 詳細データ")

# 表示用の整形
df_display = df_month[['事業所名', '営業日数', 'のべ利用者数', '平日稼働率', '土曜稼働率', '確定総売上', '確定客単価', '機会損失額']].copy()
df_display['平日稼働率'] = df_display['平日稼働率'].apply(lambda x: f"{x:.1f}%")
df_display['土曜稼働率'] = df_display['土曜稼働率'].apply(lambda x: f"{x:.1f}%")
df_display['確定総売上'] = df_display['確定総売上'].apply(lambda x: f"¥{x:,.0f}")
df_display['確定客単価'] = df_display['確定客単価'].apply(lambda x: f"¥{x:,.0f}")
df_display['機会損失額'] = df_display['機会損失額'].apply(lambda x: f"¥{x:,.0f}")

st.dataframe(df_display, use_container_width=True, hide_index=True)

# --- 印刷機能 ---
import streamlit.components.v1 as components
components.html("""
    <div class="no-print" style="text-align: center; margin-top: 30px;">
        <button style="padding: 14px 28px; background-color: #ef4444; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1.1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
        onclick="window.parent.print();">
        🖨️ 全社会議用レポートをPDFに出力する
        </button>
    </div>
""", height=100)
