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
    
    /* PDF印刷用スタイル (A4横で綺麗に収める) */
    @media print {
        @page { 
            size: A4 landscape; 
            margin: 8mm; 
        }
        body { 
            zoom: 0.70 !important; 
            -webkit-print-color-adjust: exact !important; 
            print-color-adjust: exact !important; 
        }
        [data-testid="stSidebar"], .stButton, .no-print, header, footer, [data-baseweb="tab-list"] { 
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

# 年・月の抽出
df['年'] = df['対象月'].astype(str).str.extract(r'(\d{4})')[0]
all_months = sorted(df['対象月'].astype(str).unique(), reverse=True)
all_years = sorted(df['年'].dropna().unique(), reverse=True)

# 共通フォーマット関数
def format_yen(x):
    try: return f"¥{int(x):,}"
    except: return x

def format_pct(x):
    try: return f"{float(x):.1f}%"
    except: return x

# タブ切り替え
tab1, tab2 = st.tabs(["📅 単月実績レポート", "📈 年間推移・累計データ"])

# ==============================================================================
# TAB 1: 単月実績レポート
# ==============================================================================
with tab1:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        selected_month = st.selectbox("確認する対象月を選択", all_months, index=0, key="sel_month_tab1")
    with col_t2:
        import streamlit.components.v1 as components
        components.html("""
            <style>@media print { body { display: none !important; } }</style>
            <div class="no-print" style="text-align: right; padding-top: 25px;">
                <button style="width: 100%; height: 42px; background-color: #3B82F6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
                onclick="window.parent.print();">
                    🖨️ 単月レポートをPDF出力
                </button>
            </div>
        """, height=70)

    df_month = df[df['対象月'].astype(str) == selected_month].copy()

    # 単月集計
    total_sales_m = df_month['確定総売上'].sum()
    total_users_m = df_month['延べ利用者数'].sum()
    avg_unit_price_m = total_sales_m / total_users_m if total_users_m > 0 else 0

    tot_cap_m = 0
    for _, row in df_month.iterrows():
        fac_name = row.get('事業所', '')
        users = row.get('延べ利用者数', 0)
        occ = row.get('総合稼働率', 0)
        if occ > 0:
            tot_cap_m += (users / (occ / 100))
        else:
            days = row.get('営業日数', 26)
            c_week = FACILITY_CONFIG.get(fac_name, {}).get('week', 30)
            tot_cap_m += c_week * days

    overall_occ_m = (total_users_m / tot_cap_m * 100) if tot_cap_m > 0 else 0

    st.markdown(f'<div class="report-title">🏢 {selected_month} 法人全体 経営実績サマリー</div>', unsafe_allow_html=True)

    # 4大KPIカード
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">全社 確定総売上</div>
            <div class="kpi-value kpi-sales">¥{int(total_sales_m):,}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">全社 延べ利用者数</div>
            <div class="kpi-value">{int(total_users_m):,} <span style="font-size:1.2rem;">人</span></div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">全社 総合稼働率</div>
            <div class="kpi-value" style="color: {'#16A34A' if overall_occ_m >= 80 else '#EF4444'};">{overall_occ_m:.1f} <span style="font-size:1.2rem;">%</span></div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">全社 平均客単価</div>
            <div class="kpi-value">¥{int(avg_unit_price_m):,}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # グラフ（2列）
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
            height=300, 
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
            height=300, 
            margin=dict(l=10, r=10, t=35, b=10), 
            yaxis=dict(range=[0, 110], ticksuffix='%')
        )
        st.plotly_chart(fig_occ, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

    # 事業所別 内訳表
    st.markdown("### 🏢 事業所別 実績内訳一覧")
    rows_m = []
    for _, r in df_month.iterrows():
        s = r.get('確定総売上', 0)
        u = r.get('延べ利用者数', 0)
        o = r.get('総合稼働率', 0)
        up = r.get('利用者単価', 0) or (s / u if u > 0 else 0)
        sh = (s / total_sales_m * 100) if total_sales_m > 0 else 0
        rows_m.append({
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
    rows_m.append({
        '事業所名': '【法人全体 合計/平均】',
        '確定総売上': f"¥{int(total_sales_m):,}",
        '売上シェア': "100.0%",
        '延べ利用人数': f"{int(total_users_m):,}人",
        '総合稼働率': f"{overall_occ_m:.1f}%",
        '客単価': f"¥{int(avg_unit_price_m):,}",
        '平日平均利用': f"{df_month['1日平均利用_平日'].sum():.1f}人",
        '土曜平均利用': f"{df_month['1日平均利用_土曜'].sum():.1f}人",
        '営業日数': f"{int(df_month['営業日数'].max()) if not df_month.empty else 0}日"
    })
    st.dataframe(pd.DataFrame(rows_m), use_container_width=True, hide_index=True)

    # 報告コメント一覧
    st.markdown("---")
    st.markdown(f"### 📝 {selected_month} 各事業所の報告コメント")
    for _, r in df_month.iterrows():
        with st.expander(f"📌 {r.get('事業所')} の報告事項", expanded=True):
            comm_c1, comm_c2 = st.columns(2)
            with comm_c1:
                st.markdown("<div style='font-weight:bold; color:#1E293B; margin-bottom:4px;'>【営業状況コメント】</div>", unsafe_allow_html=True)
                st.info(r.get('営業状況コメント') or '（記載なし）')
            with comm_c2:
                st.markdown("<div style='font-weight:bold; color:#1E293B; margin-bottom:4px;'>【人事・車両・インシデント等】</div>", unsafe_allow_html=True)
                st.warning(r.get('人事等コメント') or '（記載なし）')


# ==============================================================================
# TAB 2: 年間推移・累計データ
# ==============================================================================
with tab2:
    col_y1, col_y2 = st.columns([3, 1])
    with col_y1:
        default_y_idx = 0 if len(all_years) > 0 else 0
        selected_year = st.selectbox("対象年を選択", all_years, index=default_y_idx, key="sel_year_tab2")
    with col_y2:
        components.html("""
            <style>@media print { body { display: none !important; } }</style>
            <div class="no-print" style="text-align: right; padding-top: 25px;">
                <button style="width: 100%; height: 42px; background-color: #10B981; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 1rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" 
                onclick="window.parent.print();">
                    🖨️ 年間レポートをPDF出力
                </button>
            </div>
        """, height=70)

    # 選択年（または最新年）でフィルタ
    target_year = str(selected_year)
    if target_year not in all_years and len(all_years) > 0:
        target_year = all_years[0]
        
    df_year = df[df['年'] == target_year].copy()
    if df_year.empty and len(all_years) > 0:
        df_year = df[df['年'] == all_years[0]].copy()

    # 年間累計値の計算
    total_sales_y = df_year['確定総売上'].sum()
    total_users_y = df_year['延べ利用者数'].sum()
    avg_unit_price_y = total_sales_y / total_users_y if total_users_y > 0 else 0

    tot_cap_y = 0
    for _, row in df_year.iterrows():
        fac_name = row.get('事業所', '')
        users = row.get('延べ利用者数', 0)
        occ = row.get('総合稼働率', 0)
        if occ > 0:
            tot_cap_y += (users / (occ / 100))
        else:
            days = row.get('営業日数', 26)
            c_week = FACILITY_CONFIG.get(fac_name, {}).get('week', 30)
            tot_cap_y += c_week * days

    overall_occ_y = (total_users_y / tot_cap_y * 100) if tot_cap_y > 0 else 0

    st.markdown(f'<div class="report-title">📈 {target_year}年 法人全体 年間実績・推移サマリー</div>', unsafe_allow_html=True)

    # 年間4大KPIカード
    y1, y2, y3, y4 = st.columns(4)
    with y1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">年間 累計総売上</div>
            <div class="kpi-value kpi-sales">¥{int(total_sales_y):,}</div>
        </div>
        """, unsafe_allow_html=True)
    with y2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">年間 累計延べ利用者数</div>
            <div class="kpi-value">{int(total_users_y):,} <span style="font-size:1.2rem;">人</span></div>
        </div>
        """, unsafe_allow_html=True)
    with y3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">年間 平均総合稼働率</div>
            <div class="kpi-value" style="color: {'#16A34A' if overall_occ_y >= 80 else '#EF4444'};">{overall_occ_y:.1f} <span style="font-size:1.2rem;">%</span></div>
        </div>
        """, unsafe_allow_html=True)
    with y4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">年間 平均客単価</div>
            <div class="kpi-value">¥{int(avg_unit_price_y):,}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # 月次推移データの作成
    year_months = sorted(df_year['対象月'].astype(str).unique())
    monthly_trend = []
    for ym in year_months:
        df_sub_m = df_year[df_year['対象月'].astype(str) == ym]
        s_m = df_sub_m['確定総売上'].sum()
        u_m = df_sub_m['延べ利用者数'].sum()
        p_m = s_m / u_m if u_m > 0 else 0
        
        cap_m = 0
        for _, r in df_sub_m.iterrows():
            o = r.get('総合稼働率', 0)
            u = r.get('延べ利用者数', 0)
            if o > 0:
                cap_m += (u / (o / 100))
            else:
                cap_m += FACILITY_CONFIG.get(r.get('事業所', ''), {}).get('week', 30) * r.get('営業日数', 26)
        occ_m = (u_m / cap_m * 100) if cap_m > 0 else 0

        monthly_trend.append({
            '対象月': ym,
            '全社売上': int(s_m),
            '全社延べ利用者数': int(u_m),
            '全社稼働率': round(occ_m, 1),
            '客単価': int(p_m),
            '登録事業所数': f"{df_sub_m['事業所'].nunique()} 施設"
        })

    df_monthly_trend = pd.DataFrame(monthly_trend)

    if not df_monthly_trend.empty:
        # 年間グラフ（2列）
        yg_col1, yg_col2 = st.columns(2)
        with yg_col1:
            # 事業所別 積み上げ売上グラフ
            fig_stacked = go.Figure()
            colors = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6']
            for idx, fac in enumerate(FACILITY_CONFIG.keys()):
                df_fac_y = df_year[df_year['事業所'] == fac]
                sales_by_month = []
                for ym in year_months:
                    val = df_fac_y[df_fac_y['対象月'].astype(str) == ym]['確定総売上'].sum()
                    sales_by_month.append(val)
                fig_stacked.add_trace(go.Bar(
                    name=fac,
                    x=year_months,
                    y=sales_by_month,
                    marker_color=colors[idx % len(colors)]
                ))
            fig_stacked.update_layout(
                barmode='stack',
                title=dict(text='事業所別 月次売上推移（積み上げ棒グラフ）', font=dict(size=16)),
                height=320,
                margin=dict(l=10, r=10, t=35, b=10),
                yaxis=dict(title='売上（円）'),
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_stacked, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

        with yg_col2:
            # 全社稼働率の月次推移折れ線グラフ
            fig_occ_trend = go.Figure()
            fig_occ_trend.add_trace(go.Scatter(
                x=df_monthly_trend['対象月'],
                y=df_monthly_trend['全社稼働率'],
                mode='lines+markers',
                line=dict(color='#2563EB', width=3),
                name='全社稼働率'
            ))
            fig_occ_trend.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="8割ライン", annotation_position="top right")
            fig_occ_trend.update_layout(
                title=dict(text='全社 総合稼働率の推移（%）', font=dict(size=16)),
                height=320,
                margin=dict(l=10, r=10, t=35, b=10),
                yaxis=dict(range=[0, 110], ticksuffix='%')
            )
            st.plotly_chart(fig_occ_trend, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})

        # 月別実績推移テーブル
        st.markdown("### 📊 月別 実績推移一覧")
        disp_monthly = df_monthly_trend.copy()
        disp_monthly['全社売上'] = disp_monthly['全社売上'].apply(format_yen)
        disp_monthly['客単価'] = disp_monthly['客単価'].apply(format_yen)
        disp_monthly['全社延べ利用者数'] = disp_monthly['全社延べ利用者数'].apply(lambda x: f"{x:,}人")
        disp_monthly['全社稼働率'] = disp_monthly['全社稼働率'].apply(format_pct)
        
        # 累計行を追加
        summary_row = pd.DataFrame([{
            '対象月': f'【{target_year}年 累計/平均】',
            '全社売上': f"¥{int(total_sales_y):,}",
            '全社延べ利用者数': f"{int(total_users_y):,}人",
            '全社稼働率': f"{overall_occ_y:.1f}%",
            '客単価': f"¥{int(avg_unit_price_y):,}",
            '登録事業所数': '-'
        }])
        disp_monthly = pd.concat([disp_monthly, summary_row], ignore_index=True)
        st.dataframe(disp_monthly, use_container_width=True, hide_index=True)

    # 事業所別 年間累計実績テーブル
    st.markdown("---")
    st.markdown("### 🏢 事業所別 年間累計実績")
    fac_annual_rows = []
    for fac in FACILITY_CONFIG.keys():
        df_f = df_year[df_year['事業所'] == fac]
        f_sales = df_f['確定総売上'].sum()
        f_users = df_f['延べ利用者数'].sum()
        f_occ = df_f['総合稼働率'].mean() if not df_f.empty else 0
        f_price = f_sales / f_users if f_users > 0 else 0
        f_share = (f_sales / total_sales_y * 100) if total_sales_y > 0 else 0
        fac_annual_rows.append({
            '事業所名': fac,
            '年間累計総売上': f"¥{int(f_sales):,}",
            '売上シェア': f"{f_share:.1f}%",
            '年間延べ利用人数': f"{int(f_users):,}人",
            '年間平均稼働率': f"{f_occ:.1f}%",
            '年間平均客単価': f"¥{int(f_price):,}",
            'データ登録月数': f"{len(df_f)} ヶ月"
        })
    st.dataframe(pd.DataFrame(fac_annual_rows), use_container_width=True, hide_index=True)
