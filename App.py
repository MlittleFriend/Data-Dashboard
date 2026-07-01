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
# 传入当前日期参数，强制在日期变更（如 6-30 跨到 7-1）时击碎并穿透所有缓存
@st.cache_data(ttl=600)
def load_data(current_date_str):
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


# 3. 每日热点异步自动刷新机制（移除阻碍其运行的 session_state 锁）
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

        # 只要最新的数据日期比今天早，立刻强制启动爬虫管道更新数据
        if latest_date < today:
            records = fetch_finance_news(limit=5)
            if records:
                df_res = pd.DataFrame(records)
                conn = sqlite3.connect("my_data.db")
                df_res.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                print(f"[Auto Refresh] text_records updated successfully at {datetime.now()}")
                # 显式清除 load_data 的缓存，迫使下一次页面刷新直接读取最新 7-1 数据库
                load_data.clear()
    except Exception as e:
        print(f"[Auto Refresh] failed: {e}")


# 保证每次页面被打开或刷新时，都会在后台动态探测一次是否需要更新到 7-1 
threading.Thread(target=maybe_refresh_text_records, daemon=True).start()

# 获取今天的日期字符串作为缓存的“变化锚点”
today_str = datetime.now().strftime("%Y-%m-%d")
df, df_news = load_data(today_str)


# 4. 今日热点快讯滚动栏
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


# 5. 数据趋势对比图
st.subheader("📈 数据趋势对比图")
st.line_chart(data=df, x="AA", y=["BB", "CC"])


# 6. 本期宏观传导深度解析（剔除所有的无效不可见隐藏字符，全面使用纯净三引号字符串）
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
            Due to the fact that downstream demand is still in a mild recovery stage, price transmission has time lags and resistance, and some mid- and downstream enterprises face profit margin pressures. It is recommended to continuously monitor supply chain inventory cycles and order backfilling tempos.
        </p>

        <h4 style="color:#0d6efd;">💧 二、央行流动性环境</h4>
        <p style="line-height:1.8; color:#343a40;">
            央行通过公开市场操作维持流动性合理充裕，短端资金利率围绕政策利率窄幅波动。
            Under the dual objectives of stabilizing the exchange rate and preventing capital idling, monetary policy emphasizes precise targeting, and structural tools are expected to increase support for technological innovation, green transition, and inclusive finance.
        </p>

        <h4 style="color:#0d6efd;">📉 三、数据联动观察</h4>
        <p style="line-height:1.8; color:#343a40;">
            From the trajectory of columns AA / BB / CC in this table, short-term fluctuations diverge from mid- to long-term trends.
            If the scissors gap between BB and CC continues to narrow subsequently, it may mean that domestic supply-demand relations within the industry are improving; conversely, it is necessary to guard against secondary volatility risks brought by external shocks.
        </p>

        <div style="
            background:#e7f3ff;
            border-left:4px solid #0d6efd;
            padding:12px 16px;
            border-radius:8px;
            margin-top:18px;
            color:#084298;
        ">
            <b>💡 策略提示：</b>在宏观数据空窗期，建议结合高频量价指标与政策信号动态调整预期，避免对单一数据点过度反应。
        </div>
    </div>
    """
    st.markdown(macro_html, unsafe_allow_html=True)


# 7. 展示下方的数据表格
st.subheader("📋 原始数据明细")
st.dataframe(df, use_container_width=True)