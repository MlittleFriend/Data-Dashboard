import streamlit as st
import sqlite3
import pandas as pd
import threading
from datetime import datetime

# 1. 设置网页标题和图标
st.set_page_config(page_title="数据联动看板", page_icon="📊", layout="centered")
st.title("📊 每日 Excel 数据联动看板（云端版）")


# 2. 从数据库读取快讯、图表数据及动态宏观解析
# 注意：我们将 ttl 调整为 5 秒，甚至在必要时显式清除，彻底击碎缓存死锁！
@st.cache_data(ttl=5)
def load_data(current_date_str):
    conn = sqlite3.connect("my_data.db")
    df_records = pd.read_sql_query("SELECT * FROM sales_records", conn)
    
    # A. 读取今日实时热点快讯（来自新浪 7x24）
    try:
        df_news = pd.read_sql_query(
            "SELECT content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 5",
            conn,
        )
    except Exception:
        df_news = pd.DataFrame(columns=["content", "url", "publish_time"])
        
    # B. 【核心修正】强制从数据库读取最新手动维护的公众号文章 HTML 文本
    db_macro_html = None
    try:
        cursor = conn.cursor()
        # 显式检查表是否存在，并捞取最新一条记录
        cursor.execute("SELECT html_text FROM macro_analysis ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            db_macro_html = row[0]
    except Exception as e:
        print(f"[Frontend Sync Error] 读取公众号数据库失败，转为静态兜底: {e}")
        
    conn.close()
    return df_records, df_news, db_macro_html


# 3. 每日热点异步自动刷新机制
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
                conn = sqlite3.connect(DB_NAME)
                df_res.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                load_data.clear() # 显式击碎缓存
    except Exception:
        pass


# 启动后台探测线程
threading.Thread(target=maybe_refresh_text_records, daemon=True).start()

# 获取今天的日期作为缓存锚点
today_str = datetime.now().strftime("%Y-%m-%d")

# 每次刷新页面时，强行清空旧缓存，逼迫 Streamlit 去 my_data.db 里读取最新的公众号超链接
st.cache_data.clear()
df, df_news, target_macro_html = load_data(today_str)


# 4. 今日热点快讯滚动栏（保持新浪 7x24 高频更新）
if not df_news.empty:
    news_items = []
    for _, row in df_news.iterrows():
        content = row.get("content", "")
        url = row.get("url", "")
        time_str = row.get("publish_time", "")

        if url:
            item_html = f'<a href="{url}" target="_blank" style="color: #856404; text-decoration: none; font-weight: bold;">⚠️ {content}</a>'
        else:
            item_html = f"⚠️ {content}"

        if time_str:
            news_items.append(f"<b>[{time_str}]</b> {item_html}")
        else:
            news_items.append(item_html)

    news_html = "&nbsp;&nbsp;&nbsp;&nbsp;🔥&nbsp;".join(news_items)

    ticker_html = f"""
    <div style="background: linear-gradient(135deg, #fff9e6 0%, #fff3cd 100%); border-left: 6px solid #ffc107; border-radius: 12px; padding: 14px 20px; margin-bottom: 24px; box-shadow: 0 4px 14px rgba(255, 193, 7, 0.18); font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;">
        <div style="display: inline-block; color: #856404; font-weight: 700; font-size: 16px; margin-right: 12px; vertical-align: middle;">📰 今日热点快讯</div>
        <marquee behavior="scroll" direction="left" scrollamount="5" style="display: inline-block; width: calc(100% - 130px); color: #5d4a00; font-size: 15px; vertical-align: middle;">{news_html}</marquee>
    </div>
    """
    st.markdown(ticker_html, unsafe_allow_html=True)


# 5. 数据趋势对比图
st.subheader("📈 数据趋势对比图")
st.line_chart(data=df, x="AA", y=["BB", "CC"])


# 6. 本期宏观传导深度解析（彻底对齐：优先渲染手动维护的公众号文章链接卡片）
with st.expander("📊 本期宏观传导深度解析", expanded=False):
    if target_macro_html:
        # 只要数据库里有已经组装好的公众号链接 HTML，强制顶格渲染它！
        st.markdown(target_macro_html, unsafe_allow_html=True)
    else:
        # 极其严密的硬编码兜底方案（只有在数据库彻底为空时才展现）
        fallback_html = '''<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 12px; padding: 22px; border: 1px solid #dee2e6; font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;">
<h4 style="color:#0d6efd; margin-top:0;">🌐 一、PPI 成本传导链条</h4>
<p style="line-height:1.8; color:#343a40;">本期上游原材料价格波动通过 PPI 向中游制造业逐步传导。由于下游需求仍处于温和修复阶段，部分中下游企业利润率承压。</p>
<h4 style="color:#0d6efd;">💧 二、央行流动性环境</h4>
<p style="line-height:1.8; color:#343a40;">央行通过公开市场操作维持流动性合理充裕，短端资金利率围绕政策利率窄幅波动。</p>
<h4 style="color:#0d6efd;">📉 三、数据联动观察</h4>
<p style="line-height:1.8; color:#343a40;">从本表 AA / BB / CC 三列的走势来看，短期波动与中长期趋势出现分化。若后续剪刀差持续收窄，意味着供需改善。</p>
</div>'''
        st.markdown(fallback_html, unsafe_allow_html=True)


# 7. 展示下方的数据表格
st.subheader("📋 原始数据明细")
st.dataframe(df, use_container_width=True)