import streamlit as st

st.set_page_config(page_title="リハビリ教室 システム", layout="centered")

# 2つのアプリを1つにまとめるナビゲーション
pages = {
    "システムメニュー": [
        st.Page("staff_app.py", title="現場日次報告ツール", icon="📱"),
        st.Page("old_dashboard.py", title="経営会議用ダッシュボード(旧)", icon="📊"),
        st.Page("analysis_app.py", title="月次確定 分析ツール", icon="📁"),
        st.Page("corporate_app.py", title="全社・経営ダッシュボード", icon="🏢")
    ]
}

pg = st.navigation(pages)
pg.run()
