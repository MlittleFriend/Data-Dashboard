import streamlit as st
import sqlite3
import pandas as pd
import threading
from datetime import datetime
from upload_data import fetch_finance_news
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 设置网页标题和图标
st.set_page_config(page_title="数据联动看板", page_icon="📊", layout="centered")

# 注入深色科技风 CSS 样式以及滚动划入动画 JS
st.markdown("""
<style>
    /* 全局背景色与文字颜色 */
    .stApp {
        background-color: #0E1117 !important;
        color: #E0E0E0 !important;
    }
    /* 修改常规 Markdown 文字、标题、标签颜色 */
    .stMarkdown, p, span, label, h1, h2, h3, h4, h5, h6 {
        color: #E0E0E0 !important;
    }
    /* 选项卡（st.tabs）美化 */
    button[data-baseweb="tab"] {
        color: #E0E0E0 !important;
        background-color: transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #0d6efd !important;
        border-bottom-color: #0d6efd !important;
    }
    /* 列表/容器组件边框深色化 */
    div[data-testid="stExpander"] {
        background-color: #161B22 !important;
        border: 1px solid #30363D !important;
    }
    /* 美化表单和表格展示 */
    div[data-testid="stDataFrame"] {
        background-color: #161B22 !important;
    }
</style>

<script>
    (function() {
        try {
            const parentDoc = window.parent.document;
            const styleId = "scroll-slide-up-style";
            if (!parentDoc.getElementById(styleId)) {
                const style = parentDoc.createElement("style");
                style.id = styleId;
                style.innerHTML = `
                    .scroll-slide-up {
                        opacity: 0 !important;
                        transform: translateY(20px) !important;
                        transition: opacity 1.0s ease-out, transform 1.0s ease-out !important;
                    }
                    .scroll-slide-up.active {
                        opacity: 1 !important;
                        transform: translateY(0) !important;
                    }
                `;
                parentDoc.head.appendChild(style);
            }
            
            const applyScrollAnimation = () => {
                const targets = parentDoc.querySelectorAll('[data-testid="stPlotlyChart"], div[data-testid="stExpander"]');
                const observer = new IntersectionObserver((entries) => {
                    entries.forEach(entry => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('active');
                        }
                    });
                }, { threshold: 0.1 });
                
                targets.forEach(t => {
                    if (!t.classList.contains('scroll-slide-up')) {
                        t.classList.add('scroll-slide-up');
                        observer.observe(t);
                    }
                });
            };
            
            applyScrollAnimation();
            setInterval(applyScrollAnimation, 1000);
        } catch (e) {
            console.error("Scroll slide-up animation injection failed:", e);
        }
    })();
</script>
""", unsafe_allow_html=True)

st.title("📊 宏观经济数据联动看板")


# 2. 从数据库读取快讯、图表数据以及宏观分析 HTML 列表
#    ttl=5 强制每次刷新都穿透缓存，直连物理数据库拉取最新手动追更文章卡片
@st.cache_data(ttl=5)
def load_data(current_date_str):
    conn = sqlite3.connect("my_data.db")

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
            "SELECT content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 5",
            conn,
        )
    except Exception:
        df_news = pd.DataFrame(columns=["content", "url", "publish_time"])

    # 2.3 底部宏观研究成果 HTML 列表（由 upload_data.py 生成并写入 macro_analysis 表）
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
        conn = sqlite3.connect("my_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(publish_time) FROM text_records")
        result = cursor.fetchone()[0]
        conn.close()

        if not result:
            return

        latest_date = datetime.strptime(str(result).split(" ")[0], "%Y-%m-%d").date()
        today = datetime.now().date()

        if latest_date < today:
            records = fetch_finance_news(limit=5)
            if records:
                df_res = pd.DataFrame(records)
                conn = sqlite3.connect("my_data.db")
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
st.cache_data.clear()
df_trend, df_cat, df_cpi_compare, df_coal_prices, df_news, target_macro_html = load_data(today_str)


# 5. 今日热点快讯滚动栏（marquee 横向无缝滚动，每条标题可点击跳转）
if not df_news.empty:
    news_items = []
    for _, row in df_news.iterrows():
        content = row.get("content", "")
        url = row.get("url", "")
        time_str = row.get("publish_time", "")

        if url:
            item_html = (
                f'<a href="{url}" target="_blank" '
                f'style="color: #856404; text-decoration: none; font-weight: bold;">'
                f'⚠️ {content}</a>'
            )
        else:
            item_html = f"⚠️ {content}"

        if time_str:
            news_items.append(f"<b>[{time_str}]</b> {item_html}")
        else:
            news_items.append(item_html)

    news_html = "&nbsp;&nbsp;&nbsp;&nbsp;🔥&nbsp;".join(news_items)

    ticker_html = f"""
    <div style="
        background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%);
        border-left: 6px solid #ffc107;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 24px;
        box-shadow: 0 4px 14px rgba(255, 193, 7, 0.18);
        font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
    ">
        <div style="
            display: inline-block;
            color: #856404;
            font-weight: 700;
            font-size: 16px;
            margin-right: 12px;
            vertical-align: middle;
        ">
            📰 今日热点快讯
        </div>
        <marquee behavior="scroll" direction="left" scrollamount="5" style="
            display: inline-block;
            width: calc(100% - 130px);
            color: #5d4a00;
            font-size: 15px;
            vertical-align: middle;
        ">
            {news_html}
        </marquee>
    </div>
    """
    st.markdown(ticker_html, unsafe_allow_html=True)


# 6. 数据可视化分析
st.subheader("📈 宏观数据多维可视化分析")

# 1. CPI同比与核心CPI同比走势 (独占一行)
st.markdown("##### 📊 CPI同比与核心CPI同比走势")
if not df_cpi_compare.empty:
    fig_cpi = go.Figure()
    fig_cpi.add_trace(go.Scatter(
        x=df_cpi_compare["date"],
        y=df_cpi_compare["cpi_yoy"],
        mode="lines",
        name="CPI当月同比 (%)",
        line=dict(color="#0d6efd", width=2.5)
    ))
    fig_cpi.add_trace(go.Scatter(
        x=df_cpi_compare["date"],
        y=df_cpi_compare["core_cpi_yoy"],
        mode="lines",
        name="核心CPI当月同比 (%)",
        line=dict(color="#ff7f0e", width=2.5)
    ))
    fig_cpi.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        transition=dict(duration=800, easing="cubic-in-out")
    )
    fig_cpi.update_xaxes(showgrid=False, zeroline=False, linecolor="#30363d")
    fig_cpi.update_yaxes(showgrid=False, zeroline=False, linecolor="#30363d")
    st.plotly_chart(fig_cpi, use_container_width=True, config={'staticPlot': True})
else:
    st.write("暂无CPI对比数据")

# 2. 核心分项当月同比（最新月份）(独占一行)
st.markdown("##### 📊 核心分项当月同比（最新月份）")
if not df_cat.empty:
    latest_row = df_cat.iloc[-1]
    latest_date = latest_row["date"]
    
    categories = ["食品烟酒", "衣着", "居住", "生活用品", "交通通信", "文教娱乐", "医疗", "其他"]
    values = [float(latest_row[cat]) for cat in categories]
    
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=categories,
        y=values,
        name="同比增速 (%)",
        marker_color="#0d6efd",
        text=[f"{val:+.1f}%" for val in values],
        textposition="auto",
        marker=dict(line=dict(width=0))
    ))
    fig_bar.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode="x",
        transition=dict(duration=800, easing="cubic-in-out")
    )
    fig_bar.update_xaxes(showgrid=False, zeroline=False, linecolor="#30363d")
    fig_bar.update_yaxes(showgrid=False, zeroline=False, linecolor="#30363d")
    st.plotly_chart(fig_bar, use_container_width=True, config={'staticPlot': True})
else:
    st.write("暂无分项数据")

# 3. 动力煤与焦煤现货价格对比 (独占一行)
st.markdown("##### 📊 动力煤与焦煤现货价格对比")
if not df_coal_prices.empty:
    fig_coal = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 焦煤价格 -> 左 Y 轴 (secondary_y=False)
    fig_coal.add_trace(go.Scatter(
        x=df_coal_prices["date"],
        y=df_coal_prices["jm_price"],
        mode="lines",
        name="焦煤价格 (元/吨)",
        line=dict(color="#9467bd", width=2.5)
    ), secondary_y=False)
    
    # 动力煤价格 -> 右 Y 轴 (secondary_y=True)
    fig_coal.add_trace(go.Scatter(
        x=df_coal_prices["date"],
        y=df_coal_prices["dlm_price"],
        mode="lines",
        name="动力煤价格 (元/吨)",
        line=dict(color="#2ca02c", width=2.5)
    ), secondary_y=True)
    
    fig_coal.update_layout(
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=450,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        transition=dict(duration=800, easing="cubic-in-out")
    )
    fig_coal.update_xaxes(showgrid=False, zeroline=False, linecolor="#30363d")
    
    # 左 Y 轴样式 (焦煤颜色)
    fig_coal.update_yaxes(
        title_text="焦煤价格 (元/吨)", 
        title_font=dict(color="#9467bd"), 
        tickfont=dict(color="#9467bd"), 
        secondary_y=False, 
        showgrid=False, 
        zeroline=False, 
        linecolor="#30363d"
    )
    # 右 Y 轴样式 (动力煤颜色)
    fig_coal.update_yaxes(
        title_text="动力煤价格 (元/吨)", 
        title_font=dict(color="#2ca02c"), 
        tickfont=dict(color="#2ca02c"), 
        secondary_y=True, 
        showgrid=False, 
        zeroline=False, 
        linecolor="#30363d"
    )
    st.plotly_chart(fig_coal, use_container_width=True, config={'staticPlot': True})
else:
    st.write("暂无煤炭价格数据")


# 7. 本期宏观传导深度解析（已平铺至主页面，移除 st.expander 折叠）
#    优先从 macro_analysis 表读取 upload_data.py 生成的深蓝科技风 HTML 列表；
#    仅当数据库为空时才回退到本地兜底文本。
st.subheader("📊 本期宏观传导深度解析")
if target_macro_html:
    # 平铺渲染数据库中的最新宏观研究列表（含真实 mp.weixin.qq.com 链接）
    st.markdown(target_macro_html, unsafe_allow_html=True)
else:
    # 数据库尚未生成列表时的应急兜底，保留原科技感样式
    fallback_html = """
    <div style="
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 12px;
        padding: 22px;
        border: 1px solid #dee2e6;
        font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
    ">
        <h4 style="color:#0d6efd; margin-top:0;">🌐 一、PPI 成本传导链条</h4>
        <p style="line-height:1.8; color:#343a40;">
            本期上游原材料价格（能源、有色金属）波动通过 PPI 向中游制造业逐步传导。
            由于下游需求仍处于温和修复阶段，价格传导存在<strong>时滞与阻力</strong>，
            部分中下游企业利润率承压。建议持续关注产业链库存周期与订单回补节奏。
        </p>

        <h4 style="color:#0d6efd;">💧 二、央行流动性环境</h4>
        <p style="line-height:1.8; color:#343a40;">
            央行通过公开市场操作维持流动性<strong>合理充裕</strong>，短端资金利率围绕政策利率窄幅波动。
            在稳汇率与防资金空转的双重目标下，货币政策更强调<strong>精准滴灌</strong>，
            结构性工具对科技创新、绿色转型与普惠金融的支持力度有望加码。
        </p>

        <h4 style="color:#0d6efd;">📉 三、数据联动观察</h4>
        <p style="line-height:1.8; color:#343a40;">
            从本表 <strong>AA / BB / CC</strong> 三列的走势来看，短期波动与中长期趋势出现分化。
            若后续 BB 与 CC 的剪刀差持续收窄，可能意味着行业内部供需关系正在改善；
            反之则需警惕外部冲击带来的二次波动风险。
        </p>

        <div style="
            background:#e7f3ff;
            border-left:4px solid #0d6efd;
            padding:12px 16px;
            border-radius:8px;
            margin-top:18px;
            color:#084298;
        ">
            <b>💡 策略提示：</b>在宏观数据空窗期，建议结合高频量价指标与政策信号动态调整预期，
            避免对单一数据点过度反应。
        </div>
    </div>
    """
    st.markdown(fallback_html, unsafe_allow_html=True)


# 8. 展示下方的数据表格
st.subheader("📋 原始数据明细")
with st.expander("查看/隐藏 原始投研数据集", expanded=False):
    tab1, tab2, tab3, tab4 = st.tabs(["📈 CPI同比走势", "📊 核心分项当月同比", "📈 CPI与核心CPI对比", "📊 动力煤与焦煤价格"])
    with tab1:
        st.dataframe(df_trend, use_container_width=True)
    with tab2:
        st.dataframe(df_cat, use_container_width=True)
    with tab3:
        st.dataframe(df_cpi_compare, use_container_width=True)
    with tab4:
        st.dataframe(df_coal_prices, use_container_width=True)
