import io
import pandas as pd
import streamlit as st
import datetime

# --- 設定 ---
st.set_page_config(page_title="月次確定 分析ツール", layout="wide")

st.markdown("""
<style>
    .report-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1E293B;
        padding: 10px 0;
        border-bottom: 2px solid #E2E8F0;
        margin-bottom: 20px;
    }
    .kpi-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        margin-bottom: 15px;
    }
    .kpi-title {
        font-size: 0.9rem;
        color: #64748B;
        margin-bottom: 5px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #0F172A;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #475569;
    }
    .sales-highlight {
        color: #0284C7;
        font-size: 1.2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

FACILITY_CONFIG = {
    "リハビリ教室新松戸": {"week": 84, "sat": 40},
    "リハビリ教室馬橋2号館": {"week": 50, "sat": 40},
    "ことばとからだのリハビリ教室": {"week": 27, "sat": 27},
    "リハビリ教室サテライトクラス": {"week": 24, "sat": 24},
    "とばとらんどの松戸": {"week": 24, "sat": 24},
    "とばとらんどの新松戸": {"week": 24, "sat": 24}
}

st.sidebar.title("月次確定 分析ツール")
facility = st.sidebar.selectbox("対象事業所", list(FACILITY_CONFIG.keys()), index=2)
cap_week = st.sidebar.number_input("平日定員 (人)", value=FACILITY_CONFIG[facility]["week"], step=1)
cap_sat = st.sidebar.number_input("土祝定員 (人)", value=FACILITY_CONFIG[facility]["sat"], step=1)
target_rate = st.sidebar.slider("目標稼働率 (%)", 60, 100, 80, 5)

file_sales = st.sidebar.file_uploader("1. 売上台帳 (CSV)", type=['csv'])
file_sched_prev = st.sidebar.file_uploader("2. スケジュール_前月 (CSV)", type=['csv'])
file_sched_curr = st.sidebar.file_uploader("3. スケジュール_当月 (CSV)", type=['csv'])

if not file_sales or not file_sched_prev:
    st.info("👈 左のサイドバーから「売上台帳」と「前月のスケジュール」CSVファイルをアップロードしてください。")
    st.stop()

if file_sales and file_sched_prev:
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
        else:
            curr_month_str = "当月"
            occ_week_c = occ_sat_c = forecast_sales = total_users_c = 0
            users_week_c = users_sat_c = cap_week_total_c = cap_sat_total_c = 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        st.error(f"【当月スケジュール】のファイル読み込み中にエラーが発生しました。詳細: {e}")
        st.stop()


    # --- DBへ保存する機能 ---
    if st.button("データベースにこの月の実績を保存する"):
        import gspread
        from google.oauth2.service_account import Credentials
        
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        try:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
            client = gspread.authorize(creds)
            
            sheet_id = st.secrets["spreadsheet"]["id"]
            workbook = client.open_by_key(sheet_id)
            worksheet = workbook.worksheet("月次データ")
            
            new_row = [
                month_str,
                facility,
                float(confirmed_sales),
                int(total_users_p),
                float(occ_week_p),
                float(occ_sat_p),
                float(insurance_sales),
                float(selfpay_sales),
                int(cap_week),
                int(cap_sat)
            ]
            worksheet.append_row(new_row)
            st.success("✅ データベースへの保存が完了しました！")
        except Exception as db_e:
            st.error(f"データベースへの保存中にエラーが発生しました: {db_e}")


    # --- UI 描画（1ページ目） ---
    st.markdown(f'''
    <div class="report-title" style="display: flex; justify-content: space-between; align-items: baseline;">
        <div>{month_str} 確定実績レポート &nbsp;&nbsp;&nbsp; {facility}</div>
        <div style="font-size: 1.15rem; color: #475569; font-weight: bold;">設定定員: 平日 {cap_week}名 / 土祝 {cap_sat}名</div>
    </div>
    ''', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-title">売上実績</div>
            <div style="margin-top: 5px; display: flex; align-items: flex-end; flex-wrap: wrap; gap: 15px;">
                <div>確定総売上 &nbsp;&nbsp; <span class="sales-highlight">¥{confirmed_sales:,.0f}</span></div>
                <div style="font-size: 0.95rem; color: #475569; padding-bottom: 3px;">(介護保険: ¥{insurance_sales:,.0f} / 自費: ¥{selfpay_sales:,.0f})</div>
                <div>確定客単価 &nbsp;&nbsp; <span class="sales-highlight">¥{unit_price:,.0f}</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    with col2:
        wk_color = "red" if occ_week_p < target_rate else "#0F172A"
        sat_color = "red" if occ_sat_p < target_rate else "#0F172A"
        st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-title">稼働率実績 (目標: {target_rate}%)</div>
            <div style="display: flex; justify-content: space-around; margin-top: 5px;">
                <div>平日 &nbsp;&nbsp; <span style="font-size: 1.8rem; font-weight: bold; color: {wk_color};">{occ_week_p:.1f}%</span><br><span class="kpi-sub">{users_week_p} / {cap_week_total_p} 名</span></div>
                <div>土祝 &nbsp;&nbsp; <span style="font-size: 1.8rem; font-weight: bold; color: {sat_color};">{occ_sat_p:.1f}%</span><br><span class="kpi-sub">{users_sat_p} / {cap_sat_total_p} 名</span></div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
    if file_sched_curr:
        st.markdown(f'''
        <div class="report-title" style="margin-top: 40px; border-bottom: 2px dashed #CBD5E1;">
            {curr_month_str} 着地予測レポート
        </div>
        ''', unsafe_allow_html=True)
        
        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f'''
            <div class="kpi-card" style="background-color: #F0F9FF; border-color: #BAE6FD;">
                <div class="kpi-title">予測売上 (予定者数 × 前月客単価)</div>
                <div class="kpi-value">¥{forecast_sales:,.0f}</div>
                <div class="kpi-sub">総予定者数: {total_users_c} 名</div>
            </div>
            ''', unsafe_allow_html=True)
        with col4:
            wk_color_c = "red" if occ_week_c < target_rate else "#0F172A"
            sat_color_c = "red" if occ_sat_c < target_rate else "#0F172A"
            st.markdown(f'''
            <div class="kpi-card" style="background-color: #F0F9FF; border-color: #BAE6FD;">
                <div class="kpi-title">予測稼働率 (目標: {target_rate}%)</div>
                <div style="display: flex; justify-content: space-around; margin-top: 5px;">
                    <div>平日 &nbsp;&nbsp; <span style="font-size: 1.8rem; font-weight: bold; color: {wk_color_c};">{occ_week_c:.1f}%</span><br><span class="kpi-sub">{users_week_c} / {cap_week_total_c} 名</span></div>
                    <div>土祝 &nbsp;&nbsp; <span style="font-size: 1.8rem; font-weight: bold; color: {sat_color_c};">{occ_sat_c:.1f}%</span><br><span class="kpi-sub">{users_sat_c} / {cap_sat_total_c} 名</span></div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
