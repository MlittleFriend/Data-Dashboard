import streamlit as st
import sqlite3
import pandas as pd
import threading
from datetime import datetime
from upload_data import fetch_finance_news

# 1. 设置网页标题和图标
st.set_page_config(page_title="数据联动看板", page_icon="📊", layout="centered")
st.title("📊 数据联动看板（这里之后可以确定具体放什么数据）")


# 2. 从数据库读取快讯、图表数据以及宏观分析 HTML 列表
#    ttl=5 强制每次刷新都穿透缓存，直连物理数据库拉取最新手动追更文章卡片
@st.cache_data(ttl=5)
def load_data(current_date_str):
    conn = sqlite3.connect("my_data.db")

    # 2.1 Excel 数字数据
    df_records = pd.read_sql_query("SELECT * FROM sales_records", conn)

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
    return df_records, df_news, target_macro_html


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


# 保证每次页面被打开或刷新时，都会在后台动态探测一次是否需要更新	hreading.Thread(target=maybe_refresh_text_records, daemon=True).start()


# 4. 强制击穿 Streamlit 全量缓存，并以当前日期作为缓存锚点重新拉取
today_str = datetime.now().strftime("%Y-%m-%d")
st.cache_data.clear()
df, df_news, target_macro_html = load_data(today_str)


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


# 6. 数据趋势对比图
st.subheader("📈 数据趋势对比图")
st.line_chart(data=df, x="AA", y=["BB", "CC"])


# 7. 本期宏观传导深度解析（默认收起）
#    优先从 macro_analysis 表读取 upload_data.py 生成的 HTML 列表；
#    仅当数据库为空时才回退到本地兜底文本。
with st.expander("📊 本期宏观传导深度解析", expanded=False):
    if target_macro_html:
        # 顶格渲染数据库中的最新宏观研究列表（含真实 mp.weixin.qq.com 链接）
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
st.dataframe(df, use_container_width=True)
