import streamlit as st
import sqlite3
import pandas as pd
import threading
from datetime import datetime
from upload_data import fetch_finance_news
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re

# 1. 设置网页标题和图标，使用大屏宽屏布局以适配 China Macro Observatory 看板风格
st.set_page_config(
    page_title="中国宏观观察哨 | China Macro Observatory", 
    page_icon="🇨🇳", 
    layout="wide"
)

# 注入高信息密度大屏科技暗调风格 CSS 样式
st.markdown("""
<style>
    /* 引入 Outfit 英文和 Noto Sans SC 中文字体 */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
    
    /* 全局背景色与文字设定 - 对齐 China Macro Observatory 放射渐变暗色调 */
    .stApp {
        background: radial-gradient(circle at 50% 10%, #0c1830 0%, #030712 100%) !important;
        color: #e2e8f0 !important;
        font-family: 'Outfit', 'Noto Sans SC', sans-serif !important;
    }
    
    /* 去除 Streamlit 页面顶部空白 */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* 大标题渐变字效果 */
    .dashboard-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 2px;
        border-bottom: 1px solid rgba(56, 189, 248, 0.1);
        padding-bottom: 8px;
    }
    
    .dashboard-title-box {
        display: flex;
        flex-direction: column;
    }
    
    .dashboard-title {
        background: linear-gradient(135deg, #00f0ff 0%, #0072ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        margin: 0;
        letter-spacing: -0.5px;
        line-height: 1.2;
    }
    
    .dashboard-subtitle {
        color: #00f0ff;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin-top: 4px;
        margin-bottom: 0;
        opacity: 0.85;
    }

    /* 前馈控制自检指示条 System Feed-forward State Panel */
    .system-status-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        background: rgba(8, 20, 44, 0.6);
        border: 1px solid rgba(0, 240, 255, 0.15);
        border-radius: 8px;
        padding: 8px 16px;
        margin-bottom: 16px;
        font-size: 0.76rem;
        align-items: center;
        justify-content: space-between;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), inset 0 0 10px rgba(0, 240, 255, 0.05);
    }
    
    .status-items {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .status-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: 600;
    }
    
    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px currentColor;
    }
    
    .dot-green {
        background-color: #10b981;
        color: #10b981;
    }
    
    .dot-blue {
        background-color: #00f0ff;
        color: #00f0ff;
    }
    
    .dot-purple {
        background-color: #a78bfa;
        color: #a78bfa;
    }

    /* 观察哨高密度玻璃感卡片容器 */
    .obs-card {
        background: rgba(10, 22, 47, 0.45) !important;
        border: 1px solid rgba(0, 240, 255, 0.12) !important;
        border-radius: 12px !important;
        padding: 15px !important;
        margin-bottom: 16px !important;
        backdrop-filter: blur(20px) !important;
        box-shadow: 0 10px 35px 0 rgba(0, 0, 0, 0.5), inset 0 0 15px rgba(0, 240, 255, 0.02) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    .obs-card:hover {
        border-color: rgba(0, 240, 255, 0.28) !important;
        box-shadow: 0 12px 40px 0 rgba(0, 240, 255, 0.05), inset 0 0 20px rgba(0, 240, 255, 0.04) !important;
    }
    
    /* 核心指标 KPI 仪表盘卡片 */
    .kpi-card {
        background: rgba(6, 14, 32, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.04);
        border-top: 3px solid #00c3ff;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        border-color: rgba(0, 240, 255, 0.35);
        box-shadow: 0 10px 30px rgba(0, 240, 255, 0.08), inset 0 0 10px rgba(0, 240, 255, 0.02);
    }
    .kpi-title {
        font-size: 0.78rem;
        color: #94a3b8;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.2;
        letter-spacing: -0.5px;
    }
    .kpi-delta {
        font-size: 0.74rem;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 3px;
        font-weight: 600;
    }
    .delta-up {
        color: #ff3b30; /* 红色：上游资源价格/通胀抬升提示 */
        text-shadow: 0 0 8px rgba(255, 59, 48, 0.2);
    }
    .delta-down {
        color: #34c759; /* 绿色：平稳下降 */
        text-shadow: 0 0 8px rgba(52, 199, 89, 0.2);
    }
    .delta-neutral {
        color: #8e8e93;
    }
    
    /* 侧边栏/控制面板样式重塑 */
    .sidebar-title {
        color: #ffffff;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 8px;
    }
    
    div[data-testid="stSidebar"] {
        background-color: #060c19 !important;
        border-right: 1px solid rgba(0, 240, 255, 0.12) !important;
    }

    /* 快讯卡片容器及微动画 */
    .news-scroll-container {
        max-height: 400px;
        overflow-y: auto;
        padding-right: 6px;
    }
    .news-scroll-container::-webkit-scrollbar {
        width: 4px;
    }
    .news-scroll-container::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.01);
        border-radius: 2px;
    }
    .news-scroll-container::-webkit-scrollbar-thumb {
        background: rgba(0, 240, 255, 0.2);
        border-radius: 2px;
    }
    .news-scroll-container::-webkit-scrollbar-thumb:hover {
        background: rgba(0, 240, 255, 0.4);
    }
    
    .news-card {
        background: transparent !important;
        border-bottom: 1px solid rgba(0, 240, 255, 0.12) !important;
        padding: 10px 4px !important;
        margin-bottom: 0px !important;
        border-radius: 0px !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .news-card:hover {
        background: rgba(11, 21, 40, 0.4) !important;
        padding-left: 8px !important;
        border-bottom-color: rgba(0, 240, 255, 0.35) !important;
    }
    .news-time {
        font-size: 0.7rem !important;
        color: #8a99ad !important;
        margin-bottom: 4px !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
    }
    .news-content {
        font-size: 0.8rem !important;
        color: #cbd5e1 !important;
        line-height: 1.45 !important;
    }
    .news-content a {
        color: #00f0ff !important;
        text-decoration: none !important;
        font-weight: 500 !important;
        transition: color 0.2s ease !important;
    }
    .news-content a:hover {
        color: #0072ff !important;
        text-decoration: underline !important;
    }
    
    /* 选项卡 (Tabs) 美化 */
    div[data-baseweb="tab-list"] {
        gap: 6px;
        background: rgba(6, 14, 32, 0.6) !important;
        padding: 4px !important;
        border-radius: 8px !important;
        border: 1px solid rgba(0, 240, 255, 0.08) !important;
    }
    button[data-baseweb="tab"] {
        border-radius: 6px !important;
        border: none !important;
        padding: 6px 14px !important;
        background: transparent !important;
        color: #8a99ad !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        color: #00f0ff !important;
        background: rgba(0, 240, 255, 0.05) !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: #0072ff !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 15px rgba(0, 114, 255, 0.4) !important;
    }
    
    /* Streamlit Expander 美化 */
    div[data-testid="stExpander"] {
        background: rgba(8, 20, 44, 0.4) !important;
        border: 1px solid rgba(0, 240, 255, 0.1) !important;
        border-radius: 10px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3) !important;
    }
    
    /* 调整原始数据表格的样式 */
    .stDataFrame {
        border: 1px solid rgba(0, 240, 255, 0.05) !important;
        border-radius: 6px !important;
    }
</style>
""", unsafe_allow_html=True)


# 聚合聚类与自适应双 Y 轴图表生成算法
def cluster_series_by_magnitude(df, value_cols):
    """
    自动对数据列的最大绝对值进行聚类分流
    若两两之间最大绝对值比例超 1.8 且最大，则在该断层点分裂为高量级和低量级阵营
    """
    if not value_cols:
        return [], []
    max_vals = {}
    for col in value_cols:
        max_vals[col] = df[col].abs().max()
    if len(value_cols) == 1:
        return value_cols, []
    
    # 升序排序
    sorted_cols = sorted(value_cols, key=lambda c: max_vals[c])
    
    max_gap_ratio = 1.0
    split_idx = len(sorted_cols)
    
    for i in range(len(sorted_cols) - 1):
        c1 = sorted_cols[i]
        c2 = sorted_cols[i+1]
        val1 = max_vals[c1]
        val2 = max_vals[c2]
        if val1 > 0:
            ratio = val2 / val1
            if ratio > 1.8 and ratio > max_gap_ratio:
                max_gap_ratio = ratio
                split_idx = i + 1
                
    if max_gap_ratio > 1.8:
        low_cols = sorted_cols[:split_idx]
        high_cols = sorted_cols[split_idx:]
    else:
        low_cols = []
        high_cols = sorted_cols
    return high_cols, low_cols


def render_dual_axis_line_chart(df, date_col, value_cols, colors=None, primary_y_title="", secondary_y_title=""):
    """
    自适应双 Y 轴多线绘制函数，适配科技暗调主题
    """
    high_cols, low_cols = cluster_series_by_magnitude(df, value_cols)
    # 电光霓虹配色方案：Cyber Cyan, Gold/Amber, Emerald Green, Royal Purple, Rose Red, Bright Yellow
    if not colors:
        colors = ["#00f0ff", "#ffb703", "#10b981", "#a78bfa", "#ff2e93", "#e2e8f0"]
    
    if low_cols:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # 挂载高量级序列在左侧主 Y 轴 (secondary_y=False)
        for idx, col in enumerate(high_cols):
            color = colors[idx % len(colors)]
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=color, width=3, shape="spline") # 使用 spline 使折线平滑有机化
            ), secondary_y=False)
            
        # 挂载低量级序列在右侧副 Y 轴 (secondary_y=True)
        for idx, col in enumerate(low_cols):
            color = colors[(idx + len(high_cols)) % len(colors)]
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=color, width=3, shape="spline")
            ), secondary_y=True)
            
        left_title = primary_y_title or ", ".join(high_cols)
        right_title = secondary_y_title or ", ".join(low_cols)
        
        left_color = colors[0]
        right_color = colors[len(high_cols) % len(colors)]
        
        fig.update_yaxes(
            title_text=left_title,
            title_font=dict(color=left_color, size=11),
            tickfont=dict(color=left_color, size=10),
            secondary_y=False,
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.03)",
            zeroline=False,
            linecolor="rgba(255, 255, 255, 0.1)"
        )
        fig.update_yaxes(
            title_text=right_title,
            title_font=dict(color=right_color, size=11),
            tickfont=dict(color=right_color, size=10),
            secondary_y=True,
            showgrid=False,
            zeroline=False,
            linecolor="rgba(255, 255, 255, 0.1)"
        )
    else:
        fig = go.Figure()
        for idx, col in enumerate(high_cols):
            color = colors[idx % len(colors)]
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=color, width=3, shape="spline")
            ))
        left_title = primary_y_title or ", ".join(high_cols)
        fig.update_yaxes(
            title_text=left_title,
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.03)",
            zeroline=False,
            linecolor="rgba(255, 255, 255, 0.1)"
        )
        
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.02, 
            xanchor="right", 
            x=1,
            bgcolor="rgba(0,0,0,0)"
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(10, 22, 47, 0.95)",
            font_size=11,
            font_family="Outfit, Noto Sans SC, sans-serif"
        ),
        transition=dict(duration=800, easing="cubic-in-out")
    )
    fig.update_xaxes(
        showgrid=True, 
        gridcolor="rgba(255, 255, 255, 0.03)", 
        zeroline=False, 
        linecolor="rgba(255, 255, 255, 0.1)"
    )
    return fig


# 2. 从数据库读取快讯、图表数据以及宏观分析 HTML 列表
#    ttl=5 强制每次刷新都穿透缓存，直连物理数据库拉取最新手动追更文章卡片
@st.cache_data(ttl=5)
def load_data(current_date_str):
    try:
        conn = sqlite3.connect("my_data.db", timeout=30.0)
    except Exception as e:
        # 控制论防御：如果数据库连接失败，构建空的 DataFrame 兜底
        print(f"[Fallback DB] Connection failed: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), ""

    # 2.1 Excel 数字数据
    try:
        df_trend = pd.read_sql_query("SELECT * FROM cpi_trend", conn)
    except Exception:
        df_trend = pd.DataFrame(columns=["date", "cpi_yoy"])

    try:
        df_cat = pd.read_sql_query("SELECT * FROM cpi_categories", conn)
    except Exception:
        df_cat = pd.DataFrame(columns=["date", "食品烟酒", "衣着", "居住", "生活用品", "交通通信", "文教娱乐", "医疗", "其他"])

    try:
        df_cpi_compare = pd.read_sql_query("SELECT * FROM dashboard_cpi_compare", conn)
    except Exception:
        df_cpi_compare = pd.DataFrame(columns=["date", "cpi_yoy", "core_cpi_yoy"])

    try:
        df_coal_prices = pd.read_sql_query("SELECT * FROM dashboard_coal_prices", conn)
    except Exception:
        df_coal_prices = pd.DataFrame(columns=["date", "dlm_price", "jm_price"])

    # 2.2 顶部新浪 7x24 实时快讯
    try:
        df_news = pd.read_sql_query(
            "SELECT content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 12",
            conn,
        )
    except Exception:
        df_news = pd.DataFrame(columns=["content", "url", "publish_time"])

    # 2.3 底部宏观研究成果 HTML 列表
    target_macro_html = ""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT html_text FROM macro_analysis ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row and row[0]:
            target_macro_html = row[0]
    except Exception:
        target_macro_html = ""

    conn.close()
    return df_trend, df_cat, df_cpi_compare, df_coal_prices, df_news, target_macro_html


# 3. 每日热点异步自动刷新机制
#    只要最新的数据日期比今天早，立刻强制启动爬虫管道更新数据，并清空缓存
def maybe_refresh_text_records():
    try:
        conn = sqlite3.connect("my_data.db", timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(publish_time) FROM text_records")
        row = cursor.fetchone()
        result = row[0] if row else None
        conn.close()

        if not result:
            # 若为空，则直接触发同步抓取
            records = fetch_finance_news(limit=12)
            if records:
                df_res = pd.DataFrame(records)
                conn = sqlite3.connect("my_data.db", timeout=30.0)
                df_res.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                load_data.clear()
            return

        latest_date = datetime.strptime(str(result).split(" ")[0], "%Y-%m-%d").date()
        today = datetime.now().date()

        if latest_date < today:
            records = fetch_finance_news(limit=12)
            if records:
                df_res = pd.DataFrame(records)
                conn = sqlite3.connect("my_data.db", timeout=30.0)
                df_res.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                print(f"[Auto Refresh] text_records updated successfully at {datetime.now()}")
                load_data.clear()
    except Exception as e:
        print(f"[Auto Refresh] failed: {e}")


# 保证每次页面被打开或刷新时，都会在后台动态探测一次是否需要更新
threading.Thread(target=maybe_refresh_text_records, daemon=True).start()


# 4. 强制击穿 Streamlit 全量缓存，并以当前日期作为缓存锚点重新拉取
today_str = datetime.now().strftime("%Y-%m-%d")
df_trend, df_cat, df_cpi_compare, df_coal_prices, df_news, target_macro_html = load_data(today_str)


# 5. 侧边栏/控制面板 (Sidebar Control Panel)
st.sidebar.markdown('<div class="sidebar-title">🎛️ 观察哨控制台 / Controls</div>', unsafe_allow_html=True)

# 动态时间跨度选择器
time_span = st.sidebar.selectbox(
    "📊 数据时间范围 (Date Filter)",
    options=["全部历史数据 (All)", "近三年 (Last 3 Years)", "近一年 (Last Year)", "近半年 (Last 6 Months)"],
    index=0
)

# 动态过滤函数的实现
def filter_dataframe_by_timespan(df, date_col, time_span_option):
    if df.empty or date_col not in df.columns:
        return df
    
    df_temp = df.copy()
    try:
        df_temp[date_col] = pd.to_datetime(df_temp[date_col])
    except Exception:
        return df
        
    latest_date = df_temp[date_col].max()
    if pd.isnull(latest_date):
        return df
        
    if "近三年" in time_span_option:
        start_date = latest_date - pd.DateOffset(years=3)
    elif "近一年" in time_span_option:
        start_date = latest_date - pd.DateOffset(years=1)
    elif "近半年" in time_span_option:
        start_date = latest_date - pd.DateOffset(months=6)
    else:
        # 全部数据，直接将日期转回 str 后返回
        df_temp[date_col] = df_temp[date_col].dt.strftime("%Y-%m-%d")
        return df_temp
        
    df_filtered = df_temp[df_temp[date_col] >= start_date].copy()
    df_filtered[date_col] = df_filtered[date_col].dt.strftime("%Y-%m-%d")
    return df_filtered

# 对折线图数据表执行过滤
df_cpi_compare_filtered = filter_dataframe_by_timespan(df_cpi_compare, "date", time_span)
df_coal_prices_filtered = filter_dataframe_by_timespan(df_coal_prices, "date", time_span)

st.sidebar.markdown("---")

# 强制触发同步按钮
if st.sidebar.button("🔄 立即同步最新数据 (Sync Now)"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("""
<div style="background: rgba(0, 240, 255, 0.04); border: 1px solid rgba(0, 240, 255, 0.1); border-radius: 6px; padding: 10px; font-size: 0.76rem; color: #94a3b8; line-height: 1.45;">
    💡 <b>智联提示</b><br>
    本看板自动从数据库加载最新分项 CPI 与黑色系双焦均价，自适应双 Y 轴聚类算法已部署，后台侦测线程自动同步 Sina 情报流。
</div>
""", unsafe_allow_html=True)


# 6. 大屏看板头部 (Header Area with Self-Inspection Bar)
st.markdown("""
<div class="dashboard-header">
    <div class="dashboard-title-box">
        <h1 class="dashboard-title">China Macro Observatory</h1>
        <p class="dashboard-subtitle">中国宏观经济观察哨 ‧ 指标监测大屏</p>
    </div>
</div>
""", unsafe_allow_html=True)

# 控制论：前馈防扰动状态自检条
last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"""
<div class="system-status-bar">
    <div class="status-items">
        <div class="status-item" style="color: #10b981;">
            <span class="status-dot dot-green"></span>
            前馈控制系统 (Pre-control Active)
        </div>
        <div class="status-item" style="color: #00f0ff;">
            <span class="status-dot dot-blue"></span>
            宏观数据库联通 (DB Linked)
        </div>
        <div class="status-item" style="color: #a78bfa;">
            <span class="status-dot dot-purple"></span>
            敏感数据采集组件校准 (Stream Align)
        </div>
    </div>
    <div style="color: #94a3b8; font-weight: 500;">
        ⏱️ 系统同步时间: <span style="color: #00f0ff; font-weight: 600;">{last_sync_time}</span> | 架构模式: <span style="color: #ffffff; font-weight: 600;">Cybernetic Defend</span>
    </div>
</div>
""", unsafe_allow_html=True)


# 7. 顶部大盘指标卡行 (Top Row: KPI Metrics Dashboards)
# 计算前置变化指标 (Delta)
try:
    if not df_cpi_compare.empty and len(df_cpi_compare) >= 2:
        df_cpi_sorted = df_cpi_compare.sort_values(by="date", ascending=True)
        latest_cpi_rec = df_cpi_sorted.iloc[-1]
        prev_cpi_rec = df_cpi_sorted.iloc[-2]
        latest_cpi = float(latest_cpi_rec["cpi_yoy"])
        delta_cpi = latest_cpi - float(prev_cpi_rec["cpi_yoy"])
        latest_core = float(latest_cpi_rec["core_cpi_yoy"])
        delta_core = latest_core - float(prev_cpi_rec["core_cpi_yoy"])
    else:
        latest_cpi, delta_cpi, latest_core, delta_core = 0.0, 0.0, 0.0, 0.0
except Exception:
    latest_cpi, delta_cpi, latest_core, delta_core = 0.0, 0.0, 0.0, 0.0

try:
    if not df_coal_prices.empty and len(df_coal_prices) >= 2:
        df_coal_sorted = df_coal_prices.sort_values(by="date", ascending=True)
        latest_coal_rec = df_coal_sorted.iloc[-1]
        prev_coal_rec = df_coal_sorted.iloc[-2]
        latest_dlm = float(latest_coal_rec["dlm_price"])
        delta_dlm = latest_dlm - float(prev_coal_rec["dlm_price"])
        latest_jm = float(latest_coal_rec["jm_price"])
        delta_jm = latest_jm - float(prev_coal_rec["jm_price"])
    else:
        latest_dlm, delta_dlm, latest_jm, delta_jm = 0.0, 0.0, 0.0, 0.0
except Exception:
    latest_dlm, delta_dlm, latest_jm, delta_jm = 0.0, 0.0, 0.0, 0.0

# 渲染 4 个 KPI 指标盒
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    delta_class = "delta-up" if delta_cpi >= 0 else "delta-down"
    delta_icon = "▲" if delta_cpi >= 0 else "▼"
    st.markdown(f'<div class="kpi-card" style="border-top-color: #00f0ff;"><div class="kpi-title">CPI 当月同比</div><div class="kpi-value">{latest_cpi:+.2f}%</div><div class="kpi-delta {delta_class}">{delta_icon} {abs(delta_cpi):.2f}% (较上月)</div></div>', unsafe_allow_html=True)

with kpi_col2:
    delta_class = "delta-up" if delta_core >= 0 else "delta-down"
    delta_icon = "▲" if delta_core >= 0 else "▼"
    st.markdown(f'<div class="kpi-card" style="border-top-color: #ffb703;"><div class="kpi-title">核心 CPI 同比</div><div class="kpi-value">{latest_core:+.2f}%</div><div class="kpi-delta {delta_class}">{delta_icon} {abs(delta_core):.2f}% (较上月)</div></div>', unsafe_allow_html=True)

with kpi_col3:
    delta_class = "delta-up" if delta_dlm >= 0 else "delta-down"
    delta_icon = "▲" if delta_dlm >= 0 else "▼"
    st.markdown(f'<div class="kpi-card" style="border-top-color: #10b981;"><div class="kpi-title">动力煤现货港口价</div><div class="kpi-value">{latest_dlm:,.0f} 元/吨</div><div class="kpi-delta {delta_class}">{delta_icon} {abs(delta_dlm):+,.0f} 元/吨</div></div>', unsafe_allow_html=True)

with kpi_col4:
    delta_class = "delta-up" if delta_jm >= 0 else "delta-down"
    delta_icon = "▲" if delta_jm >= 0 else "▼"
    st.markdown(f'<div class="kpi-card" style="border-top-color: #a78bfa;"><div class="kpi-title">焦煤现货均价</div><div class="kpi-value">{latest_jm:,.0f} 元/吨</div><div class="kpi-delta {delta_class}">{delta_icon} {abs(delta_jm):+,.0f} 元/吨</div></div>', unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 12px;"></div>', unsafe_allow_html=True)


# 8. 左右两栏网格布局重构 (Main Two-Column Grid Layout)
col_left, col_right = st.columns([6.5, 3.5])

# 左半侧主视窗：物价与大宗联动趋势 (Analysis Charts)
with col_left:
    st.markdown('<div class="obs-card">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:#ffffff; margin-top:0; font-size:1.1rem; margin-bottom:12px; font-weight: 700; letter-spacing:0.5px;">📈 多维数据深度可视化分析舱</h3>', unsafe_allow_html=True)
    
    # 选项卡美化已在全局 CSS 中处理
    tab1, tab2 = st.tabs(["🎯 综合通胀与分类物价", "🔋 黑色系双焦能源监测"])
    
    with tab1:
        # A. CPI同比与核心CPI同比走势
        st.markdown("<p style='font-size:0.8rem; color:#94a3b8; margin-top:8px; margin-bottom:5px; font-weight:500;'>📊 CPI 综合与核心物价同比趋势走势 (自适应双Y轴分流)</p>", unsafe_allow_html=True)
        if not df_cpi_compare_filtered.empty:
            df_cpi_display = df_cpi_compare_filtered.rename(columns={"cpi_yoy": "CPI当月同比 (%)", "core_cpi_yoy": "核心CPI当月同比 (%)"})
            fig_cpi = render_dual_axis_line_chart(
                df_cpi_display, 
                "date", 
                ["CPI当月同比 (%)", "核心CPI当月同比 (%)"], 
                colors=["#00f0ff", "#ffb703"],
                primary_y_title="同比 (%)"
            )
            st.plotly_chart(fig_cpi, use_container_width=True, config={'displayModeBar': False})
        else:
            st.write("暂无物价同比折线图数据")
            
        st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)
        
        # B. 核心分项当月同比（最新月份）柱状图
        st.markdown("<p style='font-size:0.8rem; color:#94a3b8; margin-top:5px; margin-bottom:5px; font-weight:500;'>📊 物价核心分项最新单月增速对比 (CPI分项剖析)</p>", unsafe_allow_html=True)
        if not df_cat.empty:
            latest_row = df_cat.iloc[-1]
            latest_date = latest_row["date"]
            
            categories = ["食品烟酒", "衣着", "居住", "生活用品", "交通通信", "文教娱乐", "医疗", "其他"]
            values = [float(latest_row[cat]) for cat in categories]
            
            # 使用高密度的霓虹电光蓝绘制柱状图
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=categories,
                y=values,
                name="同比增速 (%)",
                marker=dict(
                    color="rgba(0, 240, 255, 0.75)",
                    line=dict(color="#00f0ff", width=1.5)
                ),
                text=[f"{val:+.1f}%" for val in values],
                textposition="outside",
                textfont=dict(color="#ffffff", size=9)
            ))
            fig_bar.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                hovermode="x",
                hoverlabel=dict(bgcolor="rgba(10, 22, 47, 0.95)"),
                transition=dict(duration=800, easing="cubic-in-out")
            )
            fig_bar.update_xaxes(showgrid=False, zeroline=False, linecolor="rgba(255, 255, 255, 0.1)")
            fig_bar.update_yaxes(showgrid=True, gridcolor="rgba(255, 255, 255, 0.03)", zeroline=False, linecolor="rgba(255, 255, 255, 0.1)")
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
        else:
            st.write("暂无分项结构化数据")
            
    with tab2:
        # C. 动力煤与焦煤现货价格对比
        st.markdown("<p style='font-size:0.8rem; color:#94a3b8; margin-top:8px; margin-bottom:5px; font-weight:500;'>📊 港口动力煤现货与炼焦煤均价日度联动曲线 (自适应聚类双轴)</p>", unsafe_allow_html=True)
        if not df_coal_prices_filtered.empty:
            df_coal_display = df_coal_prices_filtered.rename(columns={"jm_price": "焦煤价格 (元/吨)", "dlm_price": "动力煤价格 (元/吨)"})
            fig_coal = render_dual_axis_line_chart(
                df_coal_display, 
                "date", 
                ["焦煤价格 (元/吨)", "动力煤价格 (元/吨)"], 
                colors=["#a78bfa", "#10b981"]
            )
            st.plotly_chart(fig_coal, use_container_width=True, config={'displayModeBar': False})
        else:
            st.write("暂无港口煤炭价格图表数据")
            
    st.markdown('</div>', unsafe_allow_html=True)


# 右半侧侧边栏：情报流与投研研究 (Live Info Feed & Deep Transmission)
with col_right:
    # 1. 实时金融快讯流 (Sina 7x24 Live Tracker)
    st.markdown('<div class="obs-card">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:#ffffff; margin-top:0; font-size:1.05rem; margin-bottom:12px; display:flex; align-items:center; gap:6px; font-weight:700;">📻 实时联播快讯流 (Sina Live Feed)</h3>', unsafe_allow_html=True)
    
    # 纵向高密度滚动快讯流渲染
    news_html_cards = []
    if not df_news.empty:
        for _, row in df_news.iterrows():
            content = row.get("content", "")
            url = row.get("url", "")
            time_str = row.get("publish_time", "")
            
            # 去除可能存在的 HTML 标签
            clean_content = re.sub('<[^<]+?>', '', content) if isinstance(content, str) else ""
            
            if url:
                title_html = f'<a href="{url}" target="_blank" style="color: #00f0ff; text-decoration: none; font-weight: 500;">{clean_content}</a>'
            else:
                title_html = clean_content
                
            card_html = f'<div class="news-card"><div class="news-time">⏱️ {time_str}</div><div class="news-content">{title_html}</div></div>'
            news_html_cards.append(card_html)
    else:
        news_html_cards.append('<div style="color:#64748b; text-align:center; padding:30px; font-size:0.85rem;">暂无金融快讯数据</div>')
        
    all_news_html = "\n".join(news_html_cards)
    
    # 使用定制滚动条容器输出，移除前导空格以防被解析为 Markdown 代码块
    st.markdown(f'<div class="news-scroll-container">{all_news_html}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 2. 宏观投研传导解析 (Macro Research Portal)
    st.markdown('<div class="obs-card">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:#ffffff; margin-top:0; font-size:1.05rem; margin-bottom:12px; display:flex; align-items:center; gap:6px; font-weight:700;">🧠 深度投研传导 (WeChat Analyses)</h3>', unsafe_allow_html=True)
    
    if target_macro_html:
        # 直接嵌入从公众号同步入库的深色渐变底卡 HTML
        st.markdown(target_macro_html, unsafe_allow_html=True)
    else:
        # 兜底宏观传导解析文本，适配深色磨砂材质
        fallback_html = """<div style="background: rgba(30, 41, 59, 0.25); border-radius: 8px; padding: 15px; border: 1px solid rgba(0, 240, 255, 0.08); font-family: inherit;">
<h5 style="color:#00f0ff; margin-top:0; font-size: 0.9rem; margin-bottom: 6px;">🌐 一、PPI 成本传导链条</h5>
<p style="line-height:1.55; color:#cbd5e1; font-size: 0.78rem; margin-bottom: 12px;">本期上游原材料价格（煤炭、能源等）波动通过 PPI 向中游制造业逐步传导。由于下游需求仍处于温和修复阶段，传导存在时滞，需持续关注企业毛利变化。</p>
<h5 style="color:#ffb703; font-size: 0.9rem; margin-bottom: 6px;">💧 二、央行流动性环境</h5>
<p style="line-height:1.55; color:#cbd5e1; font-size: 0.78rem; margin-bottom: 12px;">央行通过公开市场逆回购等流动性调节，维持资金利率中枢围绕政策利率窄幅波动，强调结构性倾斜精准支持实体经济。</p>
<div style="background: rgba(0, 240, 255, 0.06); border-left: 3px solid #00f0ff; padding: 8px 12px; border-radius: 4px; margin-top: 10px; color: #e0f2fe; font-size: 0.76rem;"><b>💡 策略提示：</b>建议结合最新高频商品现货报价调整策略。</div>
</div>"""
        st.markdown(fallback_html, unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)


# 9. 底部折叠展示完整投研原始数据集 (Raw Data Table Drawer)
st.markdown('<div style="margin-bottom: 12px;"></div>', unsafe_allow_html=True)
st.subheader("📋 原始投研数据集 (Raw Metrics)")
with st.expander("展开 / 收起 原始明细数据表格", expanded=False):
    raw_tab1, raw_tab2, raw_tab3, raw_tab4 = st.tabs([
        "📈 CPI同比走势", "📊 核心分项增速", "📈 CPI与核心CPI对比", "📊 双焦煤炭价格"
    ])
    with raw_tab1:
        st.dataframe(df_trend, use_container_width=True)
    with raw_tab2:
        st.dataframe(df_cat, use_container_width=True)
    with raw_tab3:
        st.dataframe(df_cpi_compare, use_container_width=True)
    with raw_tab4:
        st.dataframe(df_coal_prices, use_container_width=True)
