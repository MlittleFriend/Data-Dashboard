import streamlit as st
import sqlite3
import pandas as pd
import threading
from datetime import datetime
from upload_data import fetch_finance_news

# 1. 设置网页标题和图标
st.set_page_config(page_title="数据联动看板", page_icon="📊", layout="centered")
st.title("📊 每日 Excel 数据联动看板（云端版）")


# 2. 从数据库读取快讯与图表数据
#    显式设置 ttl=3600（1 小时），防止 Streamlit 永久缓存旧数据
@st.cache_data(ttl=3600)
def load_data():
    conn = sqlite3.connect("my_data.db")
    df_records = pd.read_sql_query("SELECT * FROM sales_records", conn)
    try:
        df_news = pd.read_sql_query(
            "SELECT content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 5",
            conn,
        )
    except Exception:
        df_news = pd.DataFrame(columns=["content", "url", "publish_time"])
    conn.close()
    return df_records, df_news


# 3. 每日热点异步自动刷新兜底机制
#    当检测到 text_records 最新日期早于今天时，在后台线程静默抓取更新，
#    确保 GitHub Actions 失效时页面仍能自动获取当天热点。
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
                df = pd.DataFrame(records)
                conn = sqlite3.connect("my_data.db")
                df.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                print(f"[Auto Refresh] text_records updated at {datetime.now()}")
    except Exception as e:
        print(f"[Auto Refresh] failed: {e}")


if "data_refresh_triggered" not in st.session_state:
    st.session_state.data_refresh_triggered = True
    threading.Thread(target=maybe_refresh_text_records, daemon=True).start()


df, df_news = load_data()


# 4. 今日热点快讯滚动栏（marquee 横向无缝滚动，每条标题可点击跳转）
if not df_news.empty:
    news_items = []
    for _, row in df_news.iterrows():
        content = row.get("content", "")
        url = row.get("url", "")
        time_str = row.get("publish_time", "")

        # 如果有链接，把整条标题包裹成可点击链接；没有链接则纯文本展示
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


# 5. 使用 Streamlit 官方原生图表（完美兼容所有 Python 版本）
st.subheader("📈 数据趋势对比图")
st.line_chart(data=df, x="AA", y=["BB", "CC"])


# 6. 本期宏观传导深度解析（默认收起）
#    强制使用 st.markdown(..., unsafe_allow_html=True) 渲染纯 HTML/CSS，
#    确保 <h4>、<p>、<div> 及内联样式（如 #0d6efd 蓝色左边框）不被转义为文本。
with st.expander("📊 本期宏观传导深度解析", expanded=False):
    macro_html = """
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
    st.markdown(macro_html, unsafe_allow_html=True)


# 7. 展示下方的数据表格
st.subheader("📋 原始数据明细")
st.dataframe(df, use_container_width=True)
