import streamlit as st
import sqlite3
import pandas as pd

# 1. 设置网页标题和图标
st.set_page_config(page_title="数据联动看板", page_icon="📊", layout="centered")
st.title("📊 每日 Excel 数据联动看板（云端版）")

# 2. 读取你在数据库里的真实数据
conn = sqlite3.connect("my_data.db")
df = pd.read_sql_query("SELECT * FROM sales_records", conn)
conn.close()

# 3. 使用 Streamlit 官方原生图表（完美兼容所有 Python 版本）
st.subheader("📈 数据趋势对比图")
# 这里指定横轴为 AA，纵轴画出 BB 和 CC 两条线
st.line_chart(data=df, x="AA", y=["BB", "CC"])

# 4. 展示下方的数据表格
st.subheader("📋 原始数据明细")
st.dataframe(df, use_container_width=True)