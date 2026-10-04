import streamlit as st

st.set_page_config(page_title="リハビリ教室 システム", layout="centered")

# アプリをまとめるナビゲーション
pages = {
    "システムメニュー": [
        st.Page("analysis_app.py", title="月次確定 分析ツール", icon="📁"),
        st.Page("corporate_app.py", title="全社・経営ダッシュボード", icon="🏢")
    ]
}

pg = st.navigation(pages)
pg.run()
