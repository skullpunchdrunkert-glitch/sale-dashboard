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

facility = st.selectbox("🏢 事業所名", list(FACILITY_CONFIG.keys()))
date = st.date_input("📅 営業日", datetime.today())

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
            
            # フィードバック用の計算
            total = am_k + pm_k + day_k + am_s + pm_s + day_s
            cap = FACILITY_CONFIG[facility]["sat"] if date.weekday() == 5 else FACILITY_CONFIG[facility]["week"]
            occ = (total / cap) * 100 if cap > 0 else 0
            
            st.balloons()
            st.success("✅ スプレッドシートへの保存が完了しました！")
            
            st.markdown(f"""
            <div class="metric-box">
                <div class="sub-text">{date.strftime('%m月%d日')} の本日の稼働率</div>
                <div class="big-number">{occ:.1f}%</div>
                <div class="sub-text">利用者数: <b>{total}</b>人 / 定員: <b>{cap}</b>人</div>
            </div>
            """, unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"エラーが発生しました。権限設定などが正しいか確認してください。詳細: {e}")
