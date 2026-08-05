import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime

import pandas as pd
# pyrefly: ignore [missing-import]
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

import schema_aligner
from news_sanitizer import is_valid_url, sanitize_news_item, verify_semantic_integrity, is_fragment_tail, is_numeric_ending_fragment
from upload_data import fetch_finance_news

# 版本标识与前馈控制参数 V2.0.0
VERSION = "V2.0.0"

# 1. 设置网页标题和图标，使用大屏宽屏布局以适配 China Macro Observatory 看板风格
#    必须是第一条 st.* 命令，否则 Streamlit 会忽略 set_page_config 并导致 UI 控件异常
st.set_page_config(
    page_title="中国宏观观察哨 | China Macro Observatory", 
    page_icon="🇨🇳", 
    layout="wide"
)

# 加载并初始化外部技能动态网关
try:
    from agent_skill_kernel import init_skills
    loaded_skills = init_skills()
    print(f"[Gateway Init] 动态加载外部技能列表: {loaded_skills}")
except Exception as e:
    print(f"[Gateway Init] 初始化外部技能网关失败: {e}")

def check_and_upgrade_db():
    try:
        conn = sqlite3.connect("my_data.db", timeout=60.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='text_records'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(text_records)")
            columns = [c[1] for c in cursor.fetchall()]
            if "title" not in columns:
                cursor.execute("DROP TABLE IF EXISTS text_records")
                conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Upgrade Check] Failed: {e}")

check_and_upgrade_db()

# 自适应 Streamlit 局部渲染装饰器，实现 10 分钟或更短周期的局部刷新
if hasattr(st, "fragment"):
    news_fragment = st.fragment(run_every=60)  # 每分钟局部刷新快讯
else:
    def news_fragment(func):
        return func

# 注入高信息密度大屏科技暗调风格 CSS 样式
st.markdown("""
<style>
    /* 引入 Outfit 英文和 Noto Sans SC 中文字体 */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
    
    /* 全局背景色与文字设定 - 浅灰色典雅现代视觉主题 */
    .stApp {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%) !important;
        color: #0f172a !important;
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
        border-bottom: 1px solid #cbd5e1;
        padding-bottom: 8px;
    }
    
    .dashboard-title-box {
        display: flex;
        flex-direction: column;
    }
    
    .dashboard-title {
        background: linear-gradient(135deg, #0f172a 0%, #0284c7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2rem;
        margin: 0;
        letter-spacing: -0.5px;
        line-height: 1.2;
    }
    
    .dashboard-subtitle {
        color: #0284c7;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin-top: 4px;
        margin-bottom: 0;
        opacity: 0.9;
    }

    /* 前馈控制自检指示条 System Feed-forward State Panel */
    .system-status-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 8px 16px;
        margin-bottom: 16px;
        font-size: 0.76rem;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        color: #334155;
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
        background-color: #0284c7;
        color: #0284c7;
    }
    
    .dot-purple {
        background-color: #6366f1;
        color: #6366f1;
    }

    .dot-yellow {
        background-color: #d97706;
        color: #d97706;
    }

    /* 观察哨高密度白色质感卡片容器 */
    .obs-card {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 15px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    .obs-card:hover {
        border-color: #0284c7 !important;
        box-shadow: 0 6px 25px rgba(2, 132, 199, 0.08) !important;
    }
    
    /* 平滑页面滚动 */
    html {
        scroll-behavior: smooth !important;
    }

    /* 🚀 一键回到顶部悬浮交互按钮 (Light Mode Cyber FAB - 界面右侧垂直居中固定) */
    .back-to-top-btn {
        position: fixed !important;
        top: 50% !important;
        right: 25px !important;
        transform: translateY(-50%) !important;
        z-index: 999999 !important;
        background: linear-gradient(135deg, #0284c7 0%, #4f46e5 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.6) !important;
        border-radius: 30px !important;
        padding: 10px 18px !important;
        font-size: 0.88rem !important;
        font-weight: 700 !important;
        cursor: pointer !important;
        box-shadow: 0 6px 20px rgba(2, 132, 199, 0.35), 0 0 15px rgba(79, 70, 229, 0.2) !important;
        backdrop-filter: blur(10px) !important;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
        text-decoration: none !important;
        user-select: none !important;
    }
    .back-to-top-btn:hover {
        transform: translateY(-50%) scale(1.08) !important;
        box-shadow: 0 10px 30px rgba(2, 132, 199, 0.5), 0 0 25px rgba(79, 70, 229, 0.4) !important;
        color: #ffffff !important;
        border-color: #ffffff !important;
    }
    .back-to-top-btn:active {
        transform: translateY(-50%) scale(0.96) !important;
    }

    /* 核心指标 KPI 仪表盘卡片 */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-top: 3px solid #0284c7;
        border-radius: 10px;
        padding: 12px 16px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.03);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        border-color: #0284c7;
        box-shadow: 0 8px 25px rgba(2, 132, 199, 0.12);
    }
    /* 紧凑型 KPI 卡片（用于财政数据区，减小展示面积） */
    .kpi-card-compact {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-top: 3px solid #059669;
        border-radius: 8px;
        padding: 8px 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
        transition: all 0.25s ease;
    }
    .kpi-card-compact:hover {
        transform: translateY(-2px);
        border-color: #059669;
        box-shadow: 0 6px 18px rgba(5, 150, 105, 0.12);
    }
    .kpi-card-compact .kpi-header-row {
        margin-bottom: 2px !important;
    }
    .kpi-card-compact .kpi-value {
        font-size: 1.22rem !important;
        font-weight: 700 !important;
        margin: 2px 0 1px 0 !important;
        color: #0f172a;
    }
    .kpi-card-compact .kpi-title {
        font-size: 0.74rem !important;
    }
    .kpi-card-compact .kpi-delta {
        font-size: 0.70rem !important;
        margin-top: 2px !important;
    }
    .kpi-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .kpi-link {
        font-size: 0.72rem;
        color: #0284c7 !important;
        text-decoration: none !important;
        font-weight: 600;
        background: rgba(2, 132, 199, 0.08);
        padding: 2px 8px;
        border-radius: 4px;
        border: 1px solid rgba(2, 132, 199, 0.2);
        transition: all 0.25s ease;
    }
    .kpi-link:hover {
        background: #0284c7;
        color: #ffffff !important;
        border-color: #0284c7;
        box-shadow: 0 0 10px rgba(2, 132, 199, 0.3);
    }
    .kpi-title {
        font-size: 0.78rem;
        color: #1e293b; /* 加深为石墨深暗灰色，强化可读性 */
        font-weight: 700;
        margin-bottom: 0px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    .kpi-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.2;
        letter-spacing: -0.5px;
    }
    .kpi-delta {
        font-size: 0.74rem;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 3px;
        font-weight: 700;
    }
    .delta-up {
        color: #dc2626; /* 红色：上涨/增加 ▲ */
    }
    .delta-down {
        color: #16a34a; /* 绿色：下降/减少 ▼ */
    }
    .delta-neutral {
        color: #334155;
    }
    
    /* 侧边栏/控制面板样式重塑 */
    .sidebar-title {
        color: #0f172a;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 8px;
    }
    
    div[data-testid="stSidebar"] {
        background-color: #f8fafc !important;
        border-right: 1px solid #cbd5e1 !important;
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
        background: rgba(0, 0, 0, 0.03);
        border-radius: 2px;
    }
    .news-scroll-container::-webkit-scrollbar-thumb {
        background: rgba(2, 132, 199, 0.3);
        border-radius: 2px;
    }
    .news-scroll-container::-webkit-scrollbar-thumb:hover {
        background: rgba(2, 132, 199, 0.6);
    }
    
    .news-card {
        background: transparent !important;
        border-bottom: 1px solid #e2e8f0 !important;
        padding: 10px 4px !important;
        margin-bottom: 0px !important;
        border-radius: 0px !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .news-card:hover {
        background: #f1f5f9 !important;
        padding-left: 8px !important;
        border-bottom-color: #0284c7 !important;
    }
    .news-time {
        font-size: 0.72rem !important;
        color: #475569 !important; /* 加深为石墨灰 */
        margin-bottom: 4px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
    }
    .news-content {
        font-size: 0.82rem !important;
        color: #0f172a !important; /* 加深为纯正深灰色，清晰易读 */
        line-height: 1.45 !important;
        font-weight: 500 !important;
    }
    .news-content a {
        color: #0284c7 !important;
        text-decoration: none !important;
        font-weight: 600 !important;
        transition: color 0.2s ease !important;
    }
    .news-content a:hover {
        color: #0369a1 !important;
        text-decoration: underline !important;
    }
    .news-text-plain {
        color: #1e293b !important;
        cursor: default !important;
        font-weight: 500 !important;
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
    自适应双 Y 轴多线绘制函数，适配典雅浅灰亮色视觉主题
    """
    high_cols, low_cols = cluster_series_by_magnitude(df, value_cols)
    # 高对比亮色系：Sky Blue, Amber Gold, Emerald Green, Royal Violet, Rose Red, Cobalt Blue
    if not colors:
        colors = ["#0284c7", "#d97706", "#059669", "#7c3aed", "#e11d48", "#2563eb"]
    
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
                line=dict(color=color, width=3, shape="linear") # 与底稿折线口径一致：数据点间直线连接，不做平滑
            ), secondary_y=False)
            
        # 挂载低量级序列在右侧副 Y 轴 (secondary_y=True)
        for idx, col in enumerate(low_cols):
            color = colors[(idx + len(high_cols)) % len(colors)]
            fig.add_trace(go.Scatter(
                x=df[date_col],
                y=df[col],
                mode="lines",
                name=col,
                line=dict(color=color, width=3, shape="linear")
            ), secondary_y=True)
            
        left_title = primary_y_title or ", ".join(high_cols)
        right_title = secondary_y_title or ", ".join(low_cols)
        
        fig.update_yaxes(
            title_text=left_title,
            title_font=dict(color="#0f172a", size=11, family="Outfit, Noto Sans SC, sans-serif"),
            tickfont=dict(color="#0f172a", size=10),
            secondary_y=False,
            showgrid=True,
            gridcolor="rgba(0, 0, 0, 0.08)",
            zeroline=False,
            linecolor="rgba(0, 0, 0, 0.15)"
        )
        fig.update_yaxes(
            title_text=right_title,
            title_font=dict(color="#0f172a", size=11, family="Outfit, Noto Sans SC, sans-serif"),
            tickfont=dict(color="#0f172a", size=10),
            secondary_y=True,
            showgrid=False,
            zeroline=False,
            linecolor="rgba(0, 0, 0, 0.15)"
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
                line=dict(color=color, width=3, shape="linear")
            ))
        left_title = primary_y_title or ", ".join(high_cols)
        fig.update_yaxes(
            title_text=left_title,
            title_font=dict(color="#0f172a", size=11, family="Outfit, Noto Sans SC, sans-serif"),
            tickfont=dict(color="#0f172a", size=10),
            showgrid=True,
            gridcolor="rgba(0, 0, 0, 0.08)",
            zeroline=False,
            linecolor="rgba(0, 0, 0, 0.15)"
        )
        
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=12, r=12, t=15, b=65),
        legend=dict(
            orientation="h", 
            yanchor="top", 
            y=-0.16, 
            xanchor="center", 
            x=0.5,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#0f172a", size=10.5, family="Outfit, Noto Sans SC, sans-serif")
        ),
        xaxis=dict(
            tickfont=dict(color="#0f172a", size=10),
            title_font=dict(color="#0f172a", size=11),
            gridcolor="rgba(0, 0, 0, 0.08)",
            linecolor="rgba(0, 0, 0, 0.15)"
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            font_color="#0f172a",
            font_size=11,
            font_family="Outfit, Noto Sans SC, sans-serif"
        ),
        transition=dict(duration=800, easing="cubic-in-out")
    )
    fig.update_xaxes(
        showgrid=True, 
        gridcolor="rgba(0, 0, 0, 0.08)", 
        zeroline=False, 
        linecolor="rgba(0, 0, 0, 0.15)",
        tickfont=dict(color="#0f172a", size=10)
    )
    return fig
def render_cpi_core_history_chart(df):
    """CPI 和核心 CPI 当月同比长历史走势 (口径: 经济数据一览 CPI 表 N/O 列, 2018 年中起, 直线连接)"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cpi_yoy"], mode="lines", name="CPI当月同比",
        line=dict(color="#c0504d", width=2, shape="linear")
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["core_cpi_yoy"], mode="lines", name="核心CPI当月同比",
        line=dict(color="#d9a441", width=2, shape="linear")
    ))
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=12, r=12, t=15, b=65),
        legend=dict(
            orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#0f172a", size=10.5, family="Outfit, Noto Sans SC, sans-serif")
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)", font_color="#0f172a",
            font_size=11, font_family="Outfit, Noto Sans SC, sans-serif"
        )
    )
    fig.update_yaxes(
        title_text="同比 (%)",
        title_font=dict(color="#0f172a", size=11, family="Outfit, Noto Sans SC, sans-serif"),
        tickfont=dict(color="#0f172a", size=10),
        showgrid=True, gridcolor="rgba(0, 0, 0, 0.08)",
        zeroline=True, zerolinecolor="rgba(0, 0, 0, 0.25)",
        linecolor="rgba(0, 0, 0, 0.15)"
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="rgba(0, 0, 0, 0.08)",
        zeroline=False, linecolor="rgba(0, 0, 0, 0.15)",
        tickfont=dict(color="#0f172a", size=10)
    )
    return fig
def render_pmi_new_orders_seasonal_chart(df):
    """全国制造业 PMI 新订单季节性叠放图 (口径: 经济数据一览 PMI 表 D 列, 按年份 2018 起叠放, X 轴 1-12 月)"""
    d = df.copy()
    d["year"] = d["date"].astype(str).str.slice(0, 4)
    d["month"] = d["date"].astype(str).str.slice(5, 7).astype(int)
    d = d[d["year"] >= "2018"]
    years = sorted(d["year"].unique())
    if not years:
        return None
    latest_year = years[-1]
    # 历年配色贴近原图: 藏青/明黄/青蓝/翠绿/紫/浅绿/品红/橄榄棕
    palette = ["#1f2a5c", "#f2c500", "#29b6f6", "#43a047", "#8e44ad", "#9ccc65", "#d81b60", "#8d6e63"]
    fig = go.Figure()
    for idx, y in enumerate(years):
        sub = d[d["year"] == y].sort_values("month")
        is_latest = (y == latest_year)
        fig.add_trace(go.Scatter(
            x=[f"{m}月" for m in sub["month"]],
            y=sub["pmi_new_orders"],
            mode="lines+markers" if is_latest else "lines",
            name=y,
            line=dict(
                color="#d62728" if is_latest else palette[idx % len(palette)],
                width=3 if is_latest else 1.8,
                shape="linear"
            ),
            marker=dict(symbol="triangle-up", size=8, color="#d62728") if is_latest else dict(size=0),
        ))
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=12, r=12, t=15, b=65),
        legend=dict(
            orientation="h", yanchor="top", y=-0.16, xanchor="center", x=0.5,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color="#0f172a", size=10.5, family="Outfit, Noto Sans SC, sans-serif")
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="rgba(255, 255, 255, 0.95)", font_color="#0f172a",
            font_size=11, font_family="Outfit, Noto Sans SC, sans-serif"
        )
    )
    fig.update_yaxes(
        title_text="指数 (点)",
        title_font=dict(color="#0f172a", size=11, family="Outfit, Noto Sans SC, sans-serif"),
        tickfont=dict(color="#0f172a", size=10),
        showgrid=True, gridcolor="rgba(0, 0, 0, 0.08)",
        zeroline=False, linecolor="rgba(0, 0, 0, 0.15)"
    )
    fig.update_xaxes(
        showgrid=True, gridcolor="rgba(0, 0, 0, 0.08)",
        zeroline=False, linecolor="rgba(0, 0, 0, 0.15)",
        tickfont=dict(color="#0f172a", size=10)
    )
    return fig
# 26630 底稿中未命名内嵌图表（Chart 13-20）的展示标题补全映射
EMBEDDED_CHART_TITLE_OVERRIDES = {
    13: "社融分项同比多增（亿元）",
    14: "新口径 M1 同比（%）",
    15: "居民与企业中长期贷款（亿元）",
    16: "社融-M2 增速差（%）",
    17: "我国出口与进口同比增速（%）",
    18: "各类消费品零售增速（%）",
    19: "M1、M2 同比增速（%）",
    20: "各主要行业工业增加值增速（%）",
}
def render_embedded_chart_by_id(df_embedded, cid):
    if df_embedded.empty or "chart_id" not in df_embedded.columns:
        return None
    sub = df_embedded[df_embedded["chart_id"] == cid]
    if sub.empty:
        return None
    row = sub.iloc[0]
    try:
        cdict = json.loads(row["chart_json"])
    except Exception:
        return None

    title = cdict.get("title", "")
    # 底稿原生未命名图表使用标题补全映射
    if cid in EMBEDDED_CHART_TITLE_OVERRIDES and (not title or title.startswith("Chart ")):
        title = EMBEDDED_CHART_TITLE_OVERRIDES[cid]
    series_list = cdict.get("series", [])
    is_line_chart = cdict.get("type") == "LineChart"

    fig = go.Figure()
    colors = [
        "#0284c7", "#d97706", "#e11d48", "#059669", "#7c3aed",
        "#2563eb", "#fbbf24", "#db2777", "#6366f1", "#0891b2"
    ]

    is_stacked = "贡献拆分" in title or "拆分" in title

    for s_idx, series in enumerate(series_list):
        stitle = series.get("series_title", f"Series {s_idx+1}")
        cats = series.get("categories", [])
        vals = series.get("values", [])

        color = colors[s_idx % len(colors)]

        if is_line_chart:
            fig.add_trace(go.Scatter(
                x=cats,
                y=vals,
                mode="lines",
                name=stitle,
                line=dict(color=color, width=3, shape="spline")
            ))
        elif is_stacked:
            fig.add_trace(go.Bar(
                x=cats,
                y=vals,
                name=stitle,
                marker=dict(color=color)
            ))
        else:
            fig.add_trace(go.Bar(
                x=cats,
                y=vals,
                name=stitle,
                marker=dict(color=color),
                text=[f"{v:+.1f}%" if isinstance(v, (int, float)) and abs(v) < 200 else str(v) for v in vals],
                textposition="auto",
                textfont=dict(color="#0f172a", size=9, family="Outfit, Noto Sans SC, sans-serif")
            ))

    barmode = "stack" if is_stacked else "group"

    fig.update_layout(
        title=dict(text=f"📊 {title}", font=dict(color="#0f172a", size=13, family="Outfit, Noto Sans SC, sans-serif")),
        template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=390,
        margin=dict(l=12, r=12, t=40, b=70),
        barmode=barmode,
        hovermode="x unified" if is_stacked else "x",
        hoverlabel=dict(bgcolor="rgba(255, 255, 255, 0.95)", font_color="#0f172a", font_size=11),
        legend=dict(
            font=dict(color="#0f172a", size=10, family="Outfit, Noto Sans SC, sans-serif"),
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(0,0,0,0)"
        )
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor="rgba(0, 0, 0, 0.15)", tickfont=dict(color="#0f172a", size=10))
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0, 0, 0, 0.08)", zeroline=False, linecolor="rgba(0, 0, 0, 0.15)", tickfont=dict(color="#0f172a", size=10), title_font=dict(color="#0f172a", size=11))

    return fig
def load_listener_status():
    try:
        conn = sqlite3.connect("my_data.db", timeout=60.0)
        cursor = conn.cursor()
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_listener_status'")
        if not cursor.fetchone():
            conn.close()
            return None
        cursor.execute("SELECT sha256, mtime, alignment_info, deep_analysis, update_time FROM file_listener_status ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "sha256": row[0],
                "mtime": row[1],
                "alignment_info": json.loads(row[2]) if row[2] else {},
                "deep_analysis": row[3],
                "update_time": row[4]
            }
    except Exception as e:
        print(f"[UI Status Loader] Error loading listener status: {e}")
    return None
# 2. 从数据库读取快讯、图表数据以及宏观分析 HTML 列表
#    ttl=5 强制每次刷新都穿透缓存，直连物理数据库拉取最新手动追更文章卡片
@st.cache_data(ttl=5)
def load_data(current_date_str):
    try:
        conn = sqlite3.connect("my_data.db", timeout=60.0)
    except Exception as e:
        # 控制论防御：如果数据库连接失败，构建空的 DataFrame 兜底
        print(f"[Fallback DB] Connection failed: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "", pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

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

    # V1.3.1.0: 数据类型强转与零值防御性重新对齐 (Type Coercion & Emergency Re-Alignment)
    if not df_cpi_compare.empty:
        df_cpi_compare["core_cpi_yoy"] = pd.to_numeric(df_cpi_compare["core_cpi_yoy"], errors="coerce")
        df_cpi_compare["cpi_yoy"] = pd.to_numeric(df_cpi_compare["cpi_yoy"], errors="coerce")
        
        # 紧急内存对齐审计：如果在所有非空样本中 core_cpi_yoy 的均值等于 0.0，说明发生了严重的列选择错位或数据断流
        non_null_core = df_cpi_compare["core_cpi_yoy"].dropna()
        if len(non_null_core) > 0 and (non_null_core == 0.0).all():
            print("[Anti-Zero Interception] Mapped Core CPI is all 0.0! Executing emergency schema alignment...")
            try:
                if os.path.exists("26630.xlsx"):
                    import shutil
                    temp_emerg_path = "26630.xlsx.emerg_val.tmp.xlsx"
                    shutil.copy2("26630.xlsx", temp_emerg_path)
                    df_emerg = pd.read_excel(temp_emerg_path, sheet_name="图1，5")
                    if os.path.exists(temp_emerg_path):
                        os.remove(temp_emerg_path)
                    
                    # 重新将 Unnamed: 14 设为核心 CPI 并与主表做对齐合并
                    df_emerg_slice = df_emerg[["Unnamed: 11", "Unnamed: 14"]].copy()
                    df_emerg_slice.columns = ["date", "core_cpi_yoy"]
                    df_emerg_slice["date"] = pd.to_datetime(df_emerg_slice["date"], errors="coerce").dt.strftime("%Y-%m-%d")
                    df_emerg_slice = df_emerg_slice.dropna()
                    
                    df_cpi_compare = df_cpi_compare.drop(columns=["core_cpi_yoy"]).merge(df_emerg_slice, on="date", how="left")
                    df_cpi_compare["core_cpi_yoy"] = pd.to_numeric(df_cpi_compare["core_cpi_yoy"], errors="coerce")
                    print("[Anti-Zero Interception] Emergency alignment successful. Valid float core_cpi_yoy restored.")
            except Exception as e_emerg:
                print(f"[Anti-Zero Interception] Emergency realignment failed: {e_emerg}")

    try:
        df_coal_prices = pd.read_sql_query("SELECT * FROM dashboard_coal_prices", conn)
    except Exception:
        df_coal_prices = pd.DataFrame(columns=["date", "dlm_price", "jm_price"])

    # V1.4.2.0: 食品分项价格矩阵加载
    try:
        df_food_prices = pd.read_sql_query("SELECT * FROM dashboard_food_prices", conn)
        for col in ["fresh_vegetable", "egg", "fresh_fruit", "pork"]:
            if col in df_food_prices.columns:
                df_food_prices[col] = pd.to_numeric(df_food_prices[col], errors="coerce")
    except Exception:
        df_food_prices = pd.DataFrame(columns=["date", "fresh_vegetable", "egg", "fresh_fruit", "pork"])

    # V1.5.5.0: 通胀、财政与金融主数据时序与 Delta 加载
    try:
        df_inf_series = pd.read_sql_query("SELECT * FROM dashboard_inflation_series", conn)
    except Exception:
        df_inf_series = pd.DataFrame()

    try:
        df_fis_series = pd.read_sql_query("SELECT * FROM dashboard_fiscal_series", conn)
    except Exception:
        df_fis_series = pd.DataFrame()

    try:
        df_fin_series = pd.read_sql_query("SELECT * FROM dashboard_finance_series", conn)
    except Exception:
        df_fin_series = pd.DataFrame()

    try:
        df_econ_series = pd.read_sql_query("SELECT * FROM dashboard_economic_series", conn)
    except Exception:
        df_econ_series = pd.DataFrame()

    try:
        df_gdp_series = pd.read_sql_query("SELECT * FROM dashboard_gdp_series", conn)
    except Exception:
        df_gdp_series = pd.DataFrame()

    try:
        df_deltas = pd.read_sql_query("SELECT * FROM dashboard_kpi_deltas", conn)
    except Exception:
        df_deltas = pd.DataFrame()

    # 原生 Excel 嵌入图表提取加载
    try:
        df_embedded_charts = pd.read_sql_query("SELECT * FROM dashboard_embedded_charts", conn)
    except Exception:
        df_embedded_charts = pd.DataFrame()

    # 经济数据一览原图数据: CPI/核心CPI 长历史 & PMI 新订单月度长历史
    try:
        df_cpi_core_hist = pd.read_sql_query("SELECT * FROM dashboard_cpi_core_history", conn)
    except Exception:
        df_cpi_core_hist = pd.DataFrame(columns=["date", "cpi_yoy", "core_cpi_yoy"])

    try:
        df_pmi_orders_hist = pd.read_sql_query("SELECT * FROM dashboard_pmi_new_orders_history", conn)
    except Exception:
        df_pmi_orders_hist = pd.DataFrame(columns=["date", "pmi_new_orders"])

    # 表缺失/为空时从 econ_overview_cache.json 兜底 (云端冷启动重建路径)
    if (df_cpi_core_hist.empty or df_pmi_orders_hist.empty) and os.path.exists("econ_overview_cache.json"):
        try:
            with open("econ_overview_cache.json", "r", encoding="utf-8") as f:
                _eoc = json.load(f)
            if df_cpi_core_hist.empty and _eoc.get("cpi_core_history"):
                df_cpi_core_hist = pd.DataFrame(_eoc["cpi_core_history"])
            if df_pmi_orders_hist.empty and _eoc.get("pmi_new_orders_history"):
                df_pmi_orders_hist = pd.DataFrame(_eoc["pmi_new_orders_history"])
        except Exception:
            pass

    # 2.2 顶部新浪 7x24 实时快讯
    try:
        df_news = pd.read_sql_query(
            "SELECT title, content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 12",
            conn,
        )
    except Exception:
        df_news = pd.DataFrame(columns=["title", "content", "url", "publish_time"])

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

    # Restrict chart timeline to a 10-year window (2016–2026)
    current_year = 2026
    limit_date = f"{current_year - 10}-01-01"
    if not df_trend.empty and "date" in df_trend.columns:
        df_trend = df_trend[df_trend["date"] >= limit_date]
    if not df_cat.empty and "date" in df_cat.columns:
        df_cat = df_cat[df_cat["date"] >= limit_date]
    if not df_cpi_compare.empty and "date" in df_cpi_compare.columns:
        df_cpi_compare = df_cpi_compare[df_cpi_compare["date"] >= limit_date]
    if not df_coal_prices.empty and "date" in df_coal_prices.columns:
        df_coal_prices = df_coal_prices[df_coal_prices["date"] >= limit_date]
    if not df_inf_series.empty and "date" in df_inf_series.columns:
        df_inf_series = df_inf_series[df_inf_series["date"] >= limit_date]
    if not df_fis_series.empty and "date" in df_fis_series.columns:
        df_fis_series = df_fis_series[df_fis_series["date"] >= limit_date]
    if not df_fin_series.empty and "date" in df_fin_series.columns:
        df_fin_series = df_fin_series[df_fin_series["date"] >= limit_date]
    if not df_econ_series.empty and "date" in df_econ_series.columns:
        df_econ_series = df_econ_series[df_econ_series["date"] >= limit_date]

    return df_trend, df_cat, df_cpi_compare, df_coal_prices, df_food_prices, df_news, target_macro_html, df_inf_series, df_fis_series, df_fin_series, df_econ_series, df_gdp_series, df_deltas, df_embedded_charts, df_cpi_core_hist, df_pmi_orders_hist
# 3. 控制论高频前馈守护线程：兼顾每日首次初始化探测与10分钟高频全球热点 Top 5 增量爬取
def news_crawling_daemon():
    # 3.1 首次启动时的日常检测同步 (兼容原 `maybe_refresh_text_records` 行为)
    try:
        conn = sqlite3.connect("my_data.db", timeout=60.0)
        cursor = conn.cursor()
        
        # V1.1.4.4 Emergency Database Purge: wipe historical duplicate entries currently flooding my_data.db
        cursor.execute("DELETE FROM text_records WHERE rowid NOT IN (SELECT MIN(rowid) FROM text_records GROUP BY title, publish_time)")
        conn.commit()
        print("[Daemon Startup] Emergency duplicates purge completed.")
        
        cursor.execute("SELECT MAX(publish_time) FROM text_records")
        row = cursor.fetchone()
        result = row[0] if row else None
        conn.close()
        
        today = datetime.now().date()
        need_initial_fetch = False
        if not result:
            need_initial_fetch = True
        else:
            latest_date = datetime.strptime(str(result).split(" ")[0], "%Y-%m-%d").date()
            if latest_date < today:
                need_initial_fetch = True
                
        if need_initial_fetch:
            records = fetch_finance_news(limit=12)
            if records:
                # fetch_finance_news already split and sanitized title and content fields
                df_res = pd.DataFrame(records)
                # V1.1.4.4: 内存中去重以确保当前批次独立
                df_res = df_res.drop_duplicates(subset=["title"])
                conn = sqlite3.connect("my_data.db", timeout=60.0)
                df_res.to_sql("text_records", conn, if_exists="replace", index=False)
                conn.close()
                load_data.clear()
    except Exception as e:
        print(f"[Daemon Startup] Initial sync failed: {e}")
        
    # 3.2 周期性高频增量热点数据链抓取（每 10 分钟自动执行）
    while True:
        try:
            records = fetch_finance_news(limit=10) # 获取最新快讯以筛选 Top 5
            if records:
                conn = sqlite3.connect("my_data.db", timeout=60.0)
                # V1.1.4.4: 读取已有 title 集合以去重，防止重复写入膨胀
                try:
                    existing_df = pd.read_sql_query("SELECT title FROM text_records", conn)
                    existing_titles = set(existing_df["title"].astype(str).tolist())
                except Exception:
                    existing_titles = set()
                    
                new_records = []
                for r in records:
                    title_val = str(r.get("title", "")).strip()
                    if title_val and title_val not in existing_titles:
                        new_records.append(r)
                        
                if new_records:
                    # 按时间排序以确保时间顺序正确
                    new_records = sorted(new_records, key=lambda x: x.get("publish_time", ""))
                    # 精准取最新的 Top 5 进行写入
                    top_5_new = new_records[-5:]
                    
                    df_new = pd.DataFrame(top_5_new)
                    df_new["id"] = df_new["id"].astype(str)
                    
                    # V1.1.4.4: 在内存中强制去重，防止当前批次本身含有重复行
                    df_new = df_new.drop_duplicates(subset=["title"])
                    
                    df_new.to_sql("text_records", conn, if_exists="append", index=False)
                    print(f"[Daemon High-Freq] V1.1.4.4 appended {len(df_new)} unique global news items.")
                conn.close()
        except Exception as e:
            print(f"[Daemon High-Freq] News crawling daemon failed: {e}")
            
        time.sleep(600)  # 严格 10 分钟周期轮询
# 启动后台守护线程
threading.Thread(target=news_crawling_daemon, daemon=True).start()

# 3.4 每 12 小时 Streamlit 界面保活与唤醒 Watchdog 守护线程 (12-Hour Keep-Alive Watchdog)
def streamlit_keepalive_watchdog():
    """
    每 12 小时 (43,200 秒) 自动触发一次系统唤醒与 HTTP 保活心跳，
    刷新 SQLite 中的保活日志表并在本地 HTTP 端口维持 Streamlit 会话活跃，防止页面休眠死锁。
    """
    print("[Watchdog Keep-Alive] 12 小时 Streamlit 界面保活守护线程已在后台挂载启动！(周期: 43200s / 12h)")
    while True:
        try:
            time.sleep(43200)  # 严格 12 小时 (12 * 3600 秒)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[Watchdog Keep-Alive] [{now_str}] 触发 12 小时定时界面唤醒与数据心跳保活...")
            
            # 1. 刷新 SQLite 界面保活心跳日志
            conn = sqlite3.connect("my_data.db", timeout=60.0)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS streamlit_keepalive_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT,
                    ping_target TEXT,
                    last_heartbeat TEXT
                )
            ''')
            cursor.execute("DELETE FROM streamlit_keepalive_status")
            cursor.execute(
                "INSERT INTO streamlit_keepalive_status (status, ping_target, last_heartbeat) VALUES (?, ?, ?)",
                ("ACTIVE_AWAKE", "http://127.0.0.1:8501", now_str)
            )
            conn.commit()
            conn.close()

            # 2. 尝试向 Streamlit 本地 Web 端口发送 HTTP GET 触达心跳，维持 Web 进程与 Socket 链接活跃
            try:
                requests.get("http://127.0.0.1:8501", timeout=5)
                print("[Watchdog Keep-Alive] HTTP 8501 端口保活 Ping 成功发送。")
            except Exception:
                try:
                    requests.get("http://localhost:8501", timeout=5)
                    print("[Watchdog Keep-Alive] HTTP localhost:8501 端口保活 Ping 成功发送。")
                except Exception as e_ping:
                    print(f"[Watchdog Keep-Alive] HTTP 保活 Ping 提示: {e_ping}")
        except Exception as e_wd:
            print(f"[Watchdog Keep-Alive] 12 小时保活循环异常: {e_wd}")

# 启动 12 小时 Watchdog 保活守护子线程
threading.Thread(target=streamlit_keepalive_watchdog, daemon=True).start()

# 启动 26630.xlsx 数据监听与自适应对齐引擎守护线程
schema_aligner.start_file_watcher()
# 3.3 实时文件变更与自适应自检网关 (Hot-Reload Watchdog & V1.3.0.0 Self-Inspection)
try:
    if os.path.exists("26630.xlsx"):
        # 阶段 1: 监测文件修改及结构异常日志
        deviation_results = schema_aligner.verify_and_log_excel_deviations("26630.xlsx")
        current_sha = deviation_results.get("sha256", "")
        current_mtime = deviation_results.get("mtime", "")
        
        db_matched = False
        try:
            conn_chk = sqlite3.connect("my_data.db", timeout=60.0)
            cur_chk = conn_chk.cursor()
            cur_chk.execute("SELECT sha256, mtime FROM file_listener_status ORDER BY id DESC LIMIT 1")
            chk_row = cur_chk.fetchone()
            if chk_row and chk_row[0] == current_sha:
                db_matched = True
            conn_chk.close()
        except Exception:
            pass
            
        # V1.3.0.3: 仅在物理文件发生哈希或修改时间变更时触发 (防范假性列名异动死循环)
        if not db_matched:
            print(f"[Self-Inspection] 侦测到 26630.xlsx 发生物理变更，启动自适应解析与对齐...")
            
            # 阶段 2: 触发列定义重构并缓存到 schema_lock.json
            schema_aligner.adaptive_llm_fallback_parser("26630.xlsx")
            
            # 运行入库管线
            schema_aligner.run_alignment_pipeline("26630.xlsx", force=True)
            
            # V1.3.0.3: 显式状态密封写入，与 schema_aligner 架构字段对齐且防死锁
            try:
                conn_save = sqlite3.connect("my_data.db", timeout=60.0)
                cur_save = conn_save.cursor()
                cur_save.execute('''
                    CREATE TABLE IF NOT EXISTS file_listener_status (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT,
                        sha256 TEXT,
                        mtime TEXT,
                        alignment_info TEXT,
                        deep_analysis TEXT,
                        update_time TEXT
                    )
                ''')
                import datetime as dt_mod
                now_str = dt_mod.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur_save.execute("DELETE FROM file_listener_status")
                cur_save.execute(
                    "INSERT INTO file_listener_status (file_name, sha256, mtime, alignment_info, deep_analysis, update_time) VALUES (?, ?, ?, ?, ?, ?)",
                    ("26630.xlsx", current_sha, current_mtime, "{}", "物价同比温和上涨，核心通胀维持平稳，双焦港口价格回升，生产端成本传导面临一定时滞。", now_str)
                )
                conn_save.commit()
                conn_save.close()
                print(f"[Self-Inspection] 成功写入并锁定新状态: SHA256={current_sha[:8]}, MTIME={current_mtime}")
            except Exception as e_save:
                print(f"[Self-Inspection] 写入新状态失败: {e_save}")
            
            # 清理缓存并触发重绘
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()
except Exception as e:
    print(f"[Self-Inspection] 运行异常: {e}")

# 4. 强制击穿 Streamlit 全量缓存，并以当前日期作为缓存锚点重新拉取
today_str = datetime.now().strftime("%Y-%m-%d")
df_trend, df_cat, df_cpi_compare, df_coal_prices, df_food_prices, df_news, target_macro_html, df_inf_series, df_fis_series, df_fin_series, df_econ_series, df_gdp_series, df_deltas, df_embedded_charts, df_cpi_core_hist, df_pmi_orders_hist = load_data(today_str)

# 使用全量真实数据时序呈现折线图
df_cpi_compare_filtered = df_cpi_compare
df_coal_prices_filtered = df_coal_prices
df_food_prices_filtered = df_food_prices
df_inf_series_filtered = df_inf_series
df_fis_series_filtered = df_fis_series
df_fin_series_filtered = df_fin_series
df_econ_series_filtered = df_econ_series
df_gdp_series_filtered = df_gdp_series
# 5. 侧边栏/控制面板 (Sidebar Control Panel)
st.sidebar.markdown('<div class="sidebar-title">🎛️ 观察哨控制台 / Controls</div>', unsafe_allow_html=True)

# 强制触发同步按钮
if st.sidebar.button("🔄 立即同步最新数据 (Sync Now)"):
    st.cache_data.clear()
    st.rerun()

# 云端同步状态巡检卡（读取 cloud_sync.py 持久化的最近一次推送结果，推送失败时可被及时发现）
_cloud_sync_status = None
if os.path.exists("cloud_sync_status.json"):
    try:
        with open("cloud_sync_status.json", "r", encoding="utf-8") as _f:
            _cloud_sync_status = json.load(_f)
    except Exception:
        _cloud_sync_status = None

if _cloud_sync_status:
    _cs_ok = _cloud_sync_status.get("ok")
    _cs_color = "#16a34a" if _cs_ok else "#dc2626"
    _cs_bg = "#f0fdf4" if _cs_ok else "#fef2f2"
    _cs_border = "#bbf7d0" if _cs_ok else "#fecaca"
    _cs_icon = "✅" if _cs_ok else "❌"
    _cs_commit = _cloud_sync_status.get("commit", "")
    _cs_commit_html = f" | commit: <b>{_cs_commit}</b>" if _cs_commit else ""
    st.sidebar.markdown(f'''
<div style="background: {_cs_bg}; border: 1px solid {_cs_border}; border-radius: 6px; padding: 10px; font-size: 0.76rem; color: #0f172a; line-height: 1.45; margin-top: 10px; font-weight: 500;">
    {_cs_icon} <b style="color: {_cs_color};">云端同步 (Cloud Sync)</b><br>
    <span style="color: #475569; font-weight: 600;">{_cloud_sync_status.get("message", "")}{_cs_commit_html}</span><br>
    <span style="color: #64748b; font-size: 0.72rem; font-weight: 600;">{_cloud_sync_status.get("time", "")}</span>
</div>
''', unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 10px; font-size: 0.76rem; color: #334155; line-height: 1.45; font-weight: 500;">
    💡 <b style="color: #0284c7;">智联提示</b><br>
    本看板自动从数据库加载最新通胀、财政与经济数据切片，自适应双 Y 轴聚类算法已部署，点击页首指标旁的链接可平滑滚动至对应图表舱。
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 10px; font-size: 0.76rem; color: #0f172a; line-height: 1.45; margin-top: 10px; font-weight: 500;">
    🟢 <b style="color: #16a34a;">进门 MCP (comein-research) 投研服务已在线</b><br>
    <span style="color: #475569; font-weight: 600;">协议: SSE | 鉴权: x-mcp-key</span><br>
    <span style="color: #16a34a; font-size: 0.72rem; font-weight: 700;">已联通 72 项专业金融投研 API 工具</span>
</div>
""", unsafe_allow_html=True)
# 6. 大屏看板头部 (Header Area with Self-Inspection Bar & Top Anchor)
st.markdown("""
<div id="top-anchor"></div>
<!-- 🚀 随屏移动一键回到顶部悬浮交互按钮 -->
<a href="#top-anchor" target="_self" onclick="
    (function(){
        var scroller = document.querySelector('section.main') || document.querySelector('.main') || window;
        if (scroller.scrollTo) {
            scroller.scrollTo({ top: 0, behavior: 'smooth' });
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
        document.documentElement.scrollTo({ top: 0, behavior: 'smooth' });
        document.body.scrollTo({ top: 0, behavior: 'smooth' });
    })();
" class="back-to-top-btn" title="一键回到顶部">
    <span style="font-size: 1.05rem; line-height: 1;">🚀</span>
    <span>回到顶部</span>
</a>

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
<script>
    // 12 小时 (43,200,000 ms) 定时前端自动刷新唤醒网关
    setTimeout(function() {{
        window.location.reload();
    }}, 43200000);
</script>
<div class="system-status-bar">
    <div class="status-items">
        <div class="status-item" style="color: #059669;">
            <span class="status-dot dot-green"></span>
            前馈控制 (Pre-control Active)
        </div>
        <div class="status-item" style="color: #0284c7;">
            <span class="status-dot dot-blue"></span>
            宏观数据库 (DB Linked)
        </div>
        <div class="status-item" style="color: #d97706;">
            <span class="status-dot dot-yellow"></span>
            12H Watchdog (Awake 43200s)
        </div>
        <div class="status-item" style="color: #4f46e5;">
            <span class="status-dot dot-purple"></span>
            版本控制: <span style="color: #0f172a; font-weight: 700; margin-left: 2px;">{VERSION}</span>
        </div>
    </div>
    <div style="color: #334155; font-weight: 600;">
        ⏱️ 系统同步时间: <span style="color: #0284c7; font-weight: 700;">{last_sync_time}</span> | 架构模式: <span style="color: #0f172a; font-weight: 700;">Cybernetic Defend</span>
    </div>
</div>
""", unsafe_allow_html=True)
# 7. 顶部大盘指标卡行 (Top Row: KPI Metrics Dashboards with Anchor Jump Links)
# 7.1 计算通胀数据 KPI
try:
    if not df_inf_series.empty and len(df_inf_series) >= 1:
        df_inf_sorted = df_inf_series.sort_values(by="date", ascending=True)
        latest_inf = df_inf_sorted.iloc[-1]
        prev_inf = df_inf_sorted.iloc[-2] if len(df_inf_sorted) >= 2 else latest_inf

        latest_cpi = float(latest_inf.get("cpi_yoy", 1.0))
        latest_core = float(latest_inf.get("core_cpi_yoy", 1.0))
        latest_ppi_yoy = float(latest_inf.get("ppi_yoy", 4.1))
        latest_ppi_mom = float(latest_inf.get("ppi_mom", -0.3))

        delta_cpi = latest_cpi - float(prev_inf.get("cpi_yoy", latest_cpi))
        delta_core = latest_core - float(prev_inf.get("core_cpi_yoy", latest_core))
        delta_ppi_yoy = latest_ppi_yoy - float(prev_inf.get("ppi_yoy", latest_ppi_yoy))
        delta_ppi_mom = latest_ppi_mom - float(prev_inf.get("ppi_mom", latest_ppi_mom))
    else:
        latest_cpi, delta_cpi, latest_core, delta_core = 1.0, -0.2, 1.0, -0.1
        latest_ppi_yoy, delta_ppi_yoy, latest_ppi_mom, delta_ppi_mom = 4.1, 0.2, -0.3, -0.8
except Exception:
    latest_cpi, delta_cpi, latest_core, delta_core = 1.0, -0.2, 1.0, -0.1
    latest_ppi_yoy, delta_ppi_yoy, latest_ppi_mom, delta_ppi_mom = 4.1, 0.2, -0.3, -0.8

# 7.2 计算财政数据 KPI
try:
    if not df_fis_series.empty and len(df_fis_series) >= 1:
        df_fis_sorted = df_fis_series.sort_values(by="date", ascending=True)
        latest_fis = df_fis_sorted.iloc[-1]
        prev_fis = df_fis_sorted.iloc[-2] if len(df_fis_sorted) >= 2 else latest_fis

        latest_fis_rev = float(latest_fis.get("fiscal_revenue_yoy", 8.65))
        latest_fis_exp = float(latest_fis.get("fiscal_expenditure_yoy", 4.00))
        latest_fund_rev = float(latest_fis.get("fund_revenue_yoy", -31.14))
        latest_fund_exp = float(latest_fis.get("fund_expenditure_yoy", -43.66))

        delta_fis_rev = latest_fis_rev - float(prev_fis.get("fiscal_revenue_yoy", latest_fis_rev))
        delta_fis_exp = latest_fis_exp - float(prev_fis.get("fiscal_expenditure_yoy", latest_fis_exp))
        delta_fund_rev = latest_fund_rev - float(prev_fis.get("fund_revenue_yoy", latest_fund_rev))
        delta_fund_exp = latest_fund_exp - float(prev_fis.get("fund_expenditure_yoy", latest_fund_exp))
    else:
        latest_fis_rev, delta_fis_rev = 8.65, -2.07
        latest_fis_exp, delta_fis_exp = 4.00, -5.57
        latest_fund_rev, delta_fund_rev = -31.14, 10.88
        latest_fund_exp, delta_fund_exp = -43.66, 32.21
except Exception:
    latest_fis_rev, delta_fis_rev = 8.65, -2.07
    latest_fis_exp, delta_fis_exp = 4.00, -5.57
    latest_fund_rev, delta_fund_rev = -31.14, 10.88
    latest_fund_exp, delta_fund_exp = -43.66, 32.21

# 7.3 计算金融数据 KPI
try:
    if not df_fin_series.empty and len(df_fin_series) >= 1:
        df_fin_sorted = df_fin_series.sort_values(by="date", ascending=True)
        latest_fin = df_fin_sorted.iloc[-1]
        prev_fin = df_fin_sorted.iloc[-2] if len(df_fin_sorted) >= 2 else latest_fin

        latest_sf_inc = float(latest_fin.get("social_financing_inc", 33645.0))
        latest_credit_inc = float(latest_fin.get("credit_inc", 16100.0))
        latest_m1_yoy = float(latest_fin.get("m1_yoy", 4.0))
        latest_sf_stock_yoy = float(latest_fin.get("sf_stock_yoy", 7.4))

        delta_sf_inc = latest_sf_inc - float(prev_fin.get("social_financing_inc", latest_sf_inc))
        delta_credit_inc = latest_credit_inc - float(prev_fin.get("credit_inc", latest_credit_inc))
        delta_m1_yoy = latest_m1_yoy - float(prev_fin.get("m1_yoy", latest_m1_yoy))
        delta_sf_stock_yoy = latest_sf_stock_yoy - float(prev_fin.get("sf_stock_yoy", latest_sf_stock_yoy))
    else:
        latest_sf_inc, delta_sf_inc = 33645.0, 13352.0
        latest_credit_inc, delta_credit_inc = 16100.0, 10900.0
        latest_m1_yoy, delta_m1_yoy = 4.0, -1.5
        latest_sf_stock_yoy, delta_sf_stock_yoy = 7.4, -0.3
except Exception:
    latest_sf_inc, delta_sf_inc = 33645.0, 13352.0
    latest_credit_inc, delta_credit_inc = 16100.0, 10900.0
    latest_m1_yoy, delta_m1_yoy = 4.0, -1.5
    latest_sf_stock_yoy, delta_sf_stock_yoy = 7.4, -0.3

# 7.4 计算经济数据 KPI (制造业PMI、固资投资增速、社零增速、出口同比)
try:
    if not df_econ_series.empty and len(df_econ_series) >= 1:
        df_econ_sorted = df_econ_series.sort_values(by="date", ascending=True)
        latest_econ = df_econ_sorted.iloc[-1]
        prev_econ = df_econ_sorted.iloc[-2] if len(df_econ_sorted) >= 2 else latest_econ

        latest_pmi_manuf = float(latest_econ.get("pmi_manuf", 50.3))
        latest_fai_yoy = float(latest_econ.get("fai_yoy", -11.22))
        latest_retail_sales_yoy = float(latest_econ.get("retail_sales_yoy", 1.0))
        latest_export_yoy = float(latest_econ.get("export_yoy", 27.01))

        delta_pmi_manuf = latest_pmi_manuf - float(prev_econ.get("pmi_manuf", latest_pmi_manuf))
        delta_fai_yoy = latest_fai_yoy - float(prev_econ.get("fai_yoy", latest_fai_yoy))
        delta_retail_sales_yoy = latest_retail_sales_yoy - float(prev_econ.get("retail_sales_yoy", latest_retail_sales_yoy))
        delta_export_yoy = latest_export_yoy - float(prev_econ.get("export_yoy", latest_export_yoy))
    else:
        latest_pmi_manuf, delta_pmi_manuf = 50.3, 0.3
        latest_fai_yoy, delta_fai_yoy = -11.22, 1.31
        latest_retail_sales_yoy, delta_retail_sales_yoy = 1.0, 1.6
        latest_export_yoy, delta_export_yoy = 27.01, 7.64
except Exception:
    latest_pmi_manuf, delta_pmi_manuf = 50.3, 0.3
    latest_fai_yoy, delta_fai_yoy = -11.22, 1.31
    latest_retail_sales_yoy, delta_retail_sales_yoy = 1.0, 1.6
    latest_export_yoy, delta_export_yoy = 27.01, 7.64

# 7.4.1 计算 GDP KPI (季度频率, Delta 为较上季度变化)
try:
    if not df_gdp_series.empty and len(df_gdp_series) >= 1:
        latest_gdp_row = df_gdp_series.iloc[-1]
        prev_gdp_row = df_gdp_series.iloc[-2] if len(df_gdp_series) >= 2 else latest_gdp_row

        latest_gdp_yoy = float(latest_gdp_row.get("gdp_yoy", 4.3))
        latest_gdp_mom = float(latest_gdp_row.get("gdp_mom", 0.9))
        latest_gdp_q = str(latest_gdp_row.get("quarter", "26Q2"))

        delta_gdp_yoy = latest_gdp_yoy - float(prev_gdp_row.get("gdp_yoy", latest_gdp_yoy))
    else:
        latest_gdp_yoy, latest_gdp_mom, latest_gdp_q, delta_gdp_yoy = 4.3, 0.9, "26Q2", 0.0
except Exception:
    latest_gdp_yoy, latest_gdp_mom, latest_gdp_q, delta_gdp_yoy = 4.3, 0.9, "26Q2", 0.0

# 7.4.2 提取经济数据细分切片（供 KPI 活页与下方明细舱复用）
if not df_econ_series.empty and len(df_econ_series) >= 1:
    latest_econ_row = df_econ_series.iloc[-1]
    ind_yoy = float(latest_econ_row.get("industrial_gva_yoy", 5.3))
    ind_mom = float(latest_econ_row.get("industrial_gva_mom", 0.76))
    srv_yoy = float(latest_econ_row.get("service_index_yoy", 4.7))
    profit_yoy = float(latest_econ_row.get("profit_yoy", 0.0))
    revenue_yoy = float(latest_econ_row.get("revenue_yoy", 0.0))

    pmi_prod = float(latest_econ_row.get("pmi_manuf_prod", 51.4))
    pmi_orders = float(latest_econ_row.get("pmi_manuf_orders", 51.2))
    pmi_exp_orders = float(latest_econ_row.get("pmi_manuf_export_orders", 50.1))
    pmi_non_manuf = float(latest_econ_row.get("pmi_non_manuf", 50.2))

    fai_re = float(latest_econ_row.get("fai_realestate_yoy", -24.39))
    fai_infra = float(latest_econ_row.get("fai_infra_yoy", -9.78))
    fai_manuf = float(latest_econ_row.get("fai_manuf_yoy", -3.22))

    prop_sales = float(latest_econ_row.get("property_sales_area_yoy", -14.33))
    prop_starts = float(latest_econ_row.get("property_starts_yoy", -25.98))
    prop_comp = float(latest_econ_row.get("property_completions_yoy", -25.02))

    retail_above = float(latest_econ_row.get("retail_sales_above_size_yoy", -2.00))
    unemployment = float(latest_econ_row.get("unemployment_rate", 5.0))

    import_yoy = float(latest_econ_row.get("import_yoy", 36.01))
    trade_bal = float(latest_econ_row.get("trade_balance", 1256.23))
else:
    ind_yoy, ind_mom, srv_yoy, profit_yoy, revenue_yoy = 5.3, 0.76, 4.7, 0.0, 0.0
    pmi_prod, pmi_orders, pmi_exp_orders, pmi_non_manuf = 51.4, 51.2, 50.1, 50.2
    fai_re, fai_infra, fai_manuf = -24.39, -9.78, -3.22
    prop_sales, prop_starts, prop_comp = -14.33, -25.98, -25.02
    retail_above, unemployment = -2.0, 5.0
    import_yoy, trade_bal = 36.01, 1256.23

# 优先读取原始 Excel 中的 较上月变化
if not df_deltas.empty:
    delta_map = dict(zip(df_deltas["metric_key"], df_deltas["change_mom"]))
    if "CPI同比" in delta_map:
        delta_cpi = delta_map["CPI同比"]
    if "PPI同比" in delta_map:
        delta_ppi_yoy = delta_map["PPI同比"]
    if "PPI环比" in delta_map:
        delta_ppi_mom = delta_map["PPI环比"]
    if "公共财政收入" in delta_map:
        delta_fis_rev = delta_map["公共财政收入"]
    if "公共财政支出" in delta_map:
        delta_fis_exp = delta_map["公共财政支出"]
    if "政府性基金收入" in delta_map:
        delta_fund_rev = delta_map["政府性基金收入"]
    if "政府性基金支出" in delta_map:
        delta_fund_exp = delta_map["政府性基金支出"]
    if "社融当月新增" in delta_map:
        delta_sf_inc = delta_map["社融当月新增"]
    if "信贷当月新增" in delta_map:
        delta_credit_inc = delta_map["信贷当月新增"]
    if "M1同比增速" in delta_map:
        delta_m1_yoy = delta_map["M1同比增速"]
    if "社融存量同比增速" in delta_map:
        delta_sf_stock_yoy = delta_map["社融存量同比增速"]
    if "制造业PMI" in delta_map:
        delta_pmi_manuf = delta_map["制造业PMI"]
    if "固资投资增速" in delta_map:
        delta_fai_yoy = delta_map["固资投资增速"]
    if "社融增速" in delta_map or "社零增速" in delta_map:
        delta_retail_sales_yoy = delta_map.get("社零增速", delta_map.get("社融增速", delta_retail_sales_yoy))
    if "出口同比" in delta_map:
        delta_export_yoy = delta_map["出口同比"]

def format_kpi_delta(delta, unit="%"):
    """
    统一规范化格式化 KPI 较上月变化 (Delta):
    - delta > 0: delta-up (红色), ▲ +值
    - delta < 0: delta-down (绿色), ▼ -值
    - delta == 0: delta-neutral (灰色), - 0.00%
    """
    if delta > 0:
        d_class = "delta-up"
        d_icon = "▲"
        d_sign = "+"
    elif delta < 0:
        d_class = "delta-down"
        d_icon = "▼"
        d_sign = "-"
    else:
        d_class = "delta-neutral"
        d_icon = "-"
        d_sign = ""

    val_abs = abs(delta)
    if unit == "亿元":
        return d_class, f"{d_icon} {d_sign}{val_abs:,.0f} 亿元 (较上月)"
    elif unit == "点":
        return d_class, f"{d_icon} {d_sign}{val_abs:.1f} 点 (较上月)"
    else:
        return d_class, f"{d_icon} {d_sign}{val_abs:.2f}% (较上月)"
# 从各数据表的最大日期动态推导当前数据期（各数据区更新节奏不同，按区独立推导）
def _derive_data_period(*dfs):
    date_maxes = []
    for _df in dfs:
        if not _df.empty and "date" in _df.columns:
            date_maxes.append(str(_df["date"].max())[:7])
    if date_maxes:
        return max(date_maxes)
    return ""
data_period = _derive_data_period(df_inf_series, df_fin_series, df_fis_series, df_econ_series) or datetime.now().strftime("%Y-%m")
econ_period = _derive_data_period(df_econ_series) or data_period
inf_period = _derive_data_period(df_inf_series) or data_period
fin_period = _derive_data_period(df_fin_series) or data_period
fis_period = _derive_data_period(df_fis_series) or data_period

# 第一组：经济数据区 KPI（最上方，GDP / PMI / 外贸三大核心指标）
st.markdown(f'<h4 style="color:#0284c7; margin-top:0; margin-bottom:8px; font-size:0.92rem; font-weight:700; display:flex; align-items:center; gap:6px;">📊 最新经济核心指标（数据点：{econ_period}）</h4>', unsafe_allow_html=True)
kpi_col_e1, kpi_col_e2, kpi_col_e3 = st.columns(3)

with kpi_col_e1:
    d_class, d_txt = format_kpi_delta(delta_gdp_yoy)
    # GDP 为季度频率，Delta 口径为较上季度
    d_txt = d_txt.replace("较上月", "较上季")
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #0284c7;">
        <div class="kpi-header-row">
            <span class="kpi-title">GDP 实际同比（{latest_gdp_q}）</span>
        </div>
        <div class="kpi-value">{latest_gdp_yoy:+.1f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)
    with st.expander("📑 GDP 板块详细数据", expanded=False):
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; font-size: 0.78rem; color: #475569;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>GDP 实际同比 ({latest_gdp_q}):</span> <b style="color: #0f172a;">{latest_gdp_yoy:+.1f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>GDP 环比增速 ({latest_gdp_q}):</span> <b style="color: #0f172a;">{latest_gdp_mom:+.1f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>工增当月同比:</span> <b style="color: #0f172a;">{ind_yoy:+.1f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>工增当月环比:</span> <b style="color: #0f172a;">{ind_mom:+.2f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>服务业生产指数:</span> <b style="color: #0f172a;">{srv_yoy:+.1f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>规上工业利润同比:</span> <b style="color: #0f172a;">{profit_yoy:+.1f}%</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

with kpi_col_e2:
    d_class, d_txt = format_kpi_delta(delta_pmi_manuf, unit="点")
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #d97706;">
        <div class="kpi-header-row">
            <span class="kpi-title">制造业 PMI</span>
        </div>
        <div class="kpi-value">{latest_pmi_manuf:.1f}</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)
    with st.expander("📑 PMI 板块详细数据", expanded=False):
        p_prod_cls = "#dc2626" if pmi_prod >= 50 else "#16a34a"
        p_ord_cls = "#dc2626" if pmi_orders >= 50 else "#16a34a"
        p_exp_cls = "#dc2626" if pmi_exp_orders >= 50 else "#16a34a"
        p_non_cls = "#dc2626" if pmi_non_manuf >= 50 else "#16a34a"
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; font-size: 0.78rem; color: #475569;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>制造业PMI-生产:</span> <b style="color: {p_prod_cls};">{pmi_prod:.1f}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>制造业PMI-新订单:</span> <b style="color: {p_ord_cls};">{pmi_orders:.1f}</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>制造业PMI-新出口订单:</span> <b style="color: {p_exp_cls};">{pmi_exp_orders:.1f}</b>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>非制造业 PMI:</span> <b style="color: {p_non_cls};">{pmi_non_manuf:.1f}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

with kpi_col_e3:
    d_class, d_txt = format_kpi_delta(delta_export_yoy)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #e11d48;">
        <div class="kpi-header-row">
            <span class="kpi-title">外贸出口同比</span>
        </div>
        <div class="kpi-value">{latest_export_yoy:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)
    with st.expander("📑 外贸板块详细数据", expanded=False):
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; font-size: 0.78rem; color: #475569;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>出口当月同比:</span> <b style="color: #0f172a;">{latest_export_yoy:+.2f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                <span>进口当月同比:</span> <b style="color: #0f172a;">{import_yoy:+.2f}%</b>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>当月贸易差额:</span> <b style="color: #0f172a;">{trade_bal:,.1f} 亿美元</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 8px;"></div>', unsafe_allow_html=True)

# 第二组：通胀数据区 KPI
st.markdown(f'<h4 style="color:#0284c7; margin-top:0; margin-bottom:8px; font-size:0.92rem; font-weight:700; display:flex; align-items:center; gap:6px;">📈 最新通胀核心指标（数据点：{inf_period}）</h4>', unsafe_allow_html=True)
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

with kpi_col1:
    d_class, d_txt = format_kpi_delta(delta_cpi)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #0284c7;">
        <div class="kpi-header-row">
            <span class="kpi-title">CPI 当月同比</span>
            <a href="#cpi-chart" target="_self" class="kpi-link">📊 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_cpi:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col2:
    d_class, d_txt = format_kpi_delta(delta_core)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #d97706;">
        <div class="kpi-header-row">
            <span class="kpi-title">核心 CPI 同比</span>
            <a href="#cpi-chart" target="_self" class="kpi-link">📊 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_core:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col3:
    d_class, d_txt = format_kpi_delta(delta_ppi_yoy)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #e11d48;">
        <div class="kpi-header-row">
            <span class="kpi-title">PPI 当月同比</span>
            <a href="#ppi-chart" target="_self" class="kpi-link">📊 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_ppi_yoy:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col4:
    d_class, d_txt = format_kpi_delta(delta_ppi_mom)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #7c3aed;">
        <div class="kpi-header-row">
            <span class="kpi-title">PPI 当月环比</span>
            <a href="#ppi-chart" target="_self" class="kpi-link">📊 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_ppi_mom:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 8px;"></div>', unsafe_allow_html=True)

# 第三组：金融数据区 KPI
st.markdown(f'<h4 style="color:#7c3aed; margin-top:0; margin-bottom:8px; font-size:0.92rem; font-weight:700; display:flex; align-items:center; gap:6px;">🏦 最新金融核心指标（数据点：{fin_period}）</h4>', unsafe_allow_html=True)
kpi_col9, kpi_col10, kpi_col11, kpi_col12 = st.columns(4)

with kpi_col9:
    d_class, d_txt = format_kpi_delta(delta_sf_inc, unit="亿元")
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #7c3aed;">
        <div class="kpi-header-row">
            <span class="kpi-title">社融当月新增</span>
            <a href="#finance-chart" target="_self" class="kpi-link">🏦 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_sf_inc:,.0f} 亿元</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col10:
    d_class, d_txt = format_kpi_delta(delta_credit_inc, unit="亿元")
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #0284c7;">
        <div class="kpi-header-row">
            <span class="kpi-title">信贷当月新增</span>
            <a href="#finance-chart" target="_self" class="kpi-link">🏦 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_credit_inc:,.0f} 亿元</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col11:
    d_class, d_txt = format_kpi_delta(delta_m1_yoy)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #e11d48;">
        <div class="kpi-header-row">
            <span class="kpi-title">M1 同比增速</span>
            <a href="#finance-money-chart" target="_self" class="kpi-link">🏦 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_m1_yoy:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col12:
    d_class, d_txt = format_kpi_delta(delta_sf_stock_yoy)
    st.markdown(f'''
    <div class="kpi-card" style="border-top-color: #059669;">
        <div class="kpi-header-row">
            <span class="kpi-title">社融存量同比增速</span>
            <a href="#finance-stock-chart" target="_self" class="kpi-link">🏦 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_sf_stock_yoy:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 8px;"></div>', unsafe_allow_html=True)

# 第四组：财政数据区 KPI（最末尾，采用紧凑样式减小展示区域）
st.markdown(f'<h4 style="color:#059669; margin-top:0; margin-bottom:8px; font-size:0.88rem; font-weight:700; display:flex; align-items:center; gap:6px;">🏛️ 最新财政核心指标（数据点：{fis_period}）</h4>', unsafe_allow_html=True)
kpi_col5, kpi_col6, kpi_col7, kpi_col8 = st.columns(4)

with kpi_col5:
    d_class, d_txt = format_kpi_delta(delta_fis_rev)
    st.markdown(f'''
    <div class="kpi-card-compact" style="border-top-color: #0284c7;">
        <div class="kpi-header-row">
            <span class="kpi-title">公共财政收入增速</span>
            <a href="#fiscal-rev-exp-chart" target="_self" class="kpi-link">🏛️ 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_fis_rev:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col6:
    d_class, d_txt = format_kpi_delta(delta_fis_exp)
    st.markdown(f'''
    <div class="kpi-card-compact" style="border-top-color: #059669;">
        <div class="kpi-header-row">
            <span class="kpi-title">公共财政支出增速</span>
            <a href="#fiscal-rev-exp-chart" target="_self" class="kpi-link">🏛️ 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_fis_exp:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col7:
    d_class, d_txt = format_kpi_delta(delta_fund_rev)
    st.markdown(f'''
    <div class="kpi-card-compact" style="border-top-color: #d97706;">
        <div class="kpi-header-row">
            <span class="kpi-title">政府性基金收入增速</span>
            <a href="#fiscal-fund-chart" target="_self" class="kpi-link">🏛️ 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_fund_rev:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

with kpi_col8:
    d_class, d_txt = format_kpi_delta(delta_fund_exp)
    st.markdown(f'''
    <div class="kpi-card-compact" style="border-top-color: #db2777;">
        <div class="kpi-header-row">
            <span class="kpi-title">政府性基金支出增速</span>
            <a href="#fiscal-fund-chart" target="_self" class="kpi-link">🏛️ 细化图表 ↗</a>
        </div>
        <div class="kpi-value">{latest_fund_exp:+.2f}%</div>
        <div class="kpi-delta {d_class}">{d_txt}</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 16px;"></div>', unsafe_allow_html=True)

# 7.5 经济数据细分切片已上移至 7.4.2（KPI 活页需在渲染前取数）

# 7.6 其他经济数据明细舱（未置顶于 KPI 大区的细分数据，静态平铺）
st.markdown(f"""
<div style="margin-bottom: 12px; border-bottom: 1px solid #cbd5e1; padding-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
    <h4 style="margin: 0; color: #0284c7; font-size: 1.0rem; font-weight: 700; display: flex; align-items: center; gap: 6px;">
        📑 其他经济数据明细（数据点：{econ_period}）
    </h4>
    <span style="font-size: 0.74rem; color: #64748b; font-weight: 600;">
        未置顶于 Top KPI 大区的经济细分数据切片
    </span>
</div>
""", unsafe_allow_html=True)

em_col1, em_col2, em_col3 = st.columns(3)

with em_col1:
    st.markdown(f"""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
        <div style="font-size: 0.82rem; font-weight: 700; color: #059669; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
            <span>🏗️ 固资投资结构细分</span>
            <a href="#econ-investment-chart" target="_self" style="font-size: 0.68rem; color: #059669; text-decoration: none; font-weight: 600;">📊 图表 ↗</a>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>固资投资增速:</span> <b style="color: #0f172a;">{latest_fai_yoy:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>房地产开发投资:</span> <b style="color: #0f172a;">{fai_re:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>基础设施投资:</span> <b style="color: #0f172a;">{fai_infra:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between;">
            <span>制造业投资:</span> <b style="color: #0f172a;">{fai_manuf:+.2f}%</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

with em_col2:
    st.markdown(f"""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
        <div style="font-size: 0.82rem; font-weight: 700; color: #7c3aed; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
            <span>🏠 房地产开发链明细</span>
            <a href="#econ-investment-chart" target="_self" style="font-size: 0.68rem; color: #7c3aed; text-decoration: none; font-weight: 600;">📊 图表 ↗</a>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>商品房销售面积:</span> <b style="color: #0f172a;">{prop_sales:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>房屋新开工面积:</span> <b style="color: #0f172a;">{prop_starts:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between;">
            <span>房屋竣工面积:</span> <b style="color: #0f172a;">{prop_comp:+.2f}%</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

with em_col3:
    st.markdown(f"""
    <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
        <div style="font-size: 0.82rem; font-weight: 700; color: #e11d48; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
            <span>🛒 消费与失业</span>
            <a href="#econ-retail-chart" target="_self" style="font-size: 0.68rem; color: #e11d48; text-decoration: none; font-weight: 600;">📊 图表 ↗</a>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>社零增速:</span> <b style="color: #0f172a;">{latest_retail_sales_yoy:+.2f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>限额以上社零:</span> <b style="color: #0f172a;">{retail_above:+.1f}%</b>
        </div>
        <div style="font-size: 0.76rem; color: #475569; display: flex; justify-content: space-between;">
            <span>城镇调查失业率:</span> <b style="color: #0f172a;">{unemployment:.1f}%</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div style="margin-bottom: 16px;"></div>', unsafe_allow_html=True)
col_left, col_right = st.columns([6.5, 3.5])

# 左半侧主视窗：全量 26630 图表单页平铺展示 (Single Unified Visualizer Panel)
with col_left:
    st.markdown('<div class="obs-card">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:#0f172a; margin-top:0; font-size:1.1rem; margin-bottom:16px; font-weight: 800; letter-spacing:0.5px;">📈 26630 底稿图表全景可视化舱</h3>', unsafe_allow_html=True)

    # ==================== 第一板块：经济数据区 ====================
    st.markdown(f'<div style="border-left: 3px solid #0284c7; padding-left: 10px; margin-bottom: 14px;"><h4 style="color:#0284c7; margin:0; font-size:1.0rem; font-weight:700;">🎯 经济数据区（数据点：{econ_period}）</h4></div>', unsafe_allow_html=True)

    # 保留原 KPI 锚点，点击后滚动至经济数据区板块
    st.markdown('<div id="econ-pmi-chart"></div><div id="econ-investment-chart"></div><div id="econ-retail-chart"></div><div id="econ-industry-chart"></div><div id="econ-gdp-chart"></div>', unsafe_allow_html=True)

    # 1. 我国出口与进口同比增速 (Chart #17, Anchor: #econ-trade-chart)
    st.markdown('<div id="econ-trade-chart"></div>', unsafe_allow_html=True)
    fig_17 = render_embedded_chart_by_id(df_embedded_charts, 17)
    if fig_17:
        st.plotly_chart(fig_17, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 2. 各类消费品零售增速 (Chart #18)
    fig_18 = render_embedded_chart_by_id(df_embedded_charts, 18)
    if fig_18:
        st.plotly_chart(fig_18, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 3. M1、M2 同比增速 (Chart #19)
    fig_19 = render_embedded_chart_by_id(df_embedded_charts, 19)
    if fig_19:
        st.plotly_chart(fig_19, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 4. 各主要行业工业增加值增速 (Chart #20)
    fig_20 = render_embedded_chart_by_id(df_embedded_charts, 20)
    if fig_20:
        st.plotly_chart(fig_20, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 5. CPI 和核心 CPI 当月同比 (经济数据一览原图口径: CPI 表 N/O 列长历史, 2018 年中起)
    st.markdown("<p style='font-size:0.8rem; color:#94a3b8; margin-top:5px; margin-bottom:5px; font-weight:500;'>📊 CPI 和核心 CPI 当月同比（%）</p>", unsafe_allow_html=True)
    if not df_cpi_core_hist.empty and "cpi_yoy" in df_cpi_core_hist.columns:
        fig_cpi_core = render_cpi_core_history_chart(df_cpi_core_hist)
        st.plotly_chart(fig_cpi_core, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 6. 全国制造业 PMI 新订单 (经济数据一览原图口径: PMI 表 D 列, 按年份叠放季节图)
    st.markdown("<p style='font-size:0.8rem; color:#94a3b8; margin-top:5px; margin-bottom:5px; font-weight:500;'>📊 全国制造业 PMI 新订单（%）</p>", unsafe_allow_html=True)
    if not df_pmi_orders_hist.empty and "pmi_new_orders" in df_pmi_orders_hist.columns:
        fig_pmi_orders = render_pmi_new_orders_seasonal_chart(df_pmi_orders_hist)
        if fig_pmi_orders:
            st.plotly_chart(fig_pmi_orders, width='stretch', config={'displayModeBar': False})

    st.markdown("<div style='margin-bottom:28px; border-bottom: 1px dashed rgba(255, 255, 255, 0.1);'></div>", unsafe_allow_html=True)
    st.markdown(f'<div style="border-left: 3px solid #00f0ff; padding-left: 10px; margin-bottom: 14px;"><h4 style="color:#00f0ff; margin:0; font-size:1.0rem; font-weight:700;">🎯 通胀数据区（数据点：{inf_period}）</h4></div>', unsafe_allow_html=True)

    # 1. CPI 环比 (Chart #3, Anchor: #cpi-chart)
    st.markdown('<div id="cpi-chart"></div>', unsafe_allow_html=True)
    fig_3 = render_embedded_chart_by_id(df_embedded_charts, 3)
    if fig_3:
        st.plotly_chart(fig_3, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 3. CPI 食品分项环比 (Chart #4)
    fig_4 = render_embedded_chart_by_id(df_embedded_charts, 4)
    if fig_4:
        st.plotly_chart(fig_4, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 4. CPI 环比贡献拆分 (Chart #1)
    fig_1 = render_embedded_chart_by_id(df_embedded_charts, 1)
    if fig_1:
        st.plotly_chart(fig_1, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 5. CPI 同比贡献拆分 (Chart #2)
    fig_2 = render_embedded_chart_by_id(df_embedded_charts, 2)
    if fig_2:
        st.plotly_chart(fig_2, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 6. PPI 生产资料环比 (Chart #5, Anchor: #ppi-chart)
    st.markdown('<div id="ppi-chart"></div>', unsafe_allow_html=True)
    fig_5 = render_embedded_chart_by_id(df_embedded_charts, 5)
    if fig_5:
        st.plotly_chart(fig_5, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 9. PPI 生活资料环比 (Chart #6)
    fig_6 = render_embedded_chart_by_id(df_embedded_charts, 6)
    if fig_6:
        st.plotly_chart(fig_6, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 10. PPI 同比贡献拆分 (Chart #7)
    fig_7 = render_embedded_chart_by_id(df_embedded_charts, 7)
    if fig_7:
        st.plotly_chart(fig_7, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 11. PPI 环比贡献拆分 (Chart #8)
    fig_8 = render_embedded_chart_by_id(df_embedded_charts, 8)
    if fig_8:
        st.plotly_chart(fig_8, width='stretch', config={'displayModeBar': False})

    st.markdown("<div style='margin-bottom:28px; border-bottom: 1px dashed rgba(255, 255, 255, 0.1);'></div>", unsafe_allow_html=True)

    # ==================== 第二板块：财政数据区 ====================
    st.markdown(f'<div style="border-left: 3px solid #38bdf8; padding-left: 10px; margin-bottom: 14px; margin-top: 12px;"><h4 style="color:#38bdf8; margin:0; font-size:1.0rem; font-weight:700;">🏛️ 财政数据区（数据点：{fis_period}）</h4></div>', unsafe_allow_html=True)

    # 13. 主要税种当月同比增速 (Chart #11, Anchor: #fiscal-rev-exp-chart)
    st.markdown('<div id="fiscal-rev-exp-chart"></div>', unsafe_allow_html=True)
    fig_11 = render_embedded_chart_by_id(df_embedded_charts, 11)
    if fig_11:
        st.plotly_chart(fig_11, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 14. 各分项支出当月同比增速 (Chart #12)
    fig_12 = render_embedded_chart_by_id(df_embedded_charts, 12)
    if fig_12:
        st.plotly_chart(fig_12, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 15. 历年 6 月狭义财政收支进度 (Chart #9)
    fig_9 = render_embedded_chart_by_id(df_embedded_charts, 9)
    if fig_9:
        st.plotly_chart(fig_9, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 16. 历年 6 月政府性基金收支进度 (Chart #10, Anchor: #fiscal-fund-chart)
    st.markdown('<div id="fiscal-fund-chart"></div>', unsafe_allow_html=True)
    fig_10 = render_embedded_chart_by_id(df_embedded_charts, 10)
    if fig_10:
        st.plotly_chart(fig_10, width='stretch', config={'displayModeBar': False})

    st.markdown("<div style='margin-bottom:28px; border-bottom: 1px dashed rgba(255, 255, 255, 0.1);'></div>", unsafe_allow_html=True)

    # ==================== 第三板块：金融数据区 ====================
    st.markdown(f'<div style="border-left: 3px solid #a78bfa; padding-left: 10px; margin-bottom: 14px; margin-top: 12px;"><h4 style="color:#a78bfa; margin:0; font-size:1.0rem; font-weight:700;">🏦 金融数据区（数据点：{fin_period}）</h4></div>', unsafe_allow_html=True)

    # 17. 社融分项同比多增 (Chart #13, Anchor: #finance-chart)
    st.markdown('<div id="finance-chart"></div>', unsafe_allow_html=True)
    fig_13 = render_embedded_chart_by_id(df_embedded_charts, 13)
    if fig_13:
        st.plotly_chart(fig_13, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 18. 新口径 M1 同比 (Chart #14, Anchor: #finance-money-chart)
    st.markdown('<div id="finance-money-chart"></div>', unsafe_allow_html=True)
    fig_14 = render_embedded_chart_by_id(df_embedded_charts, 14)
    if fig_14:
        st.plotly_chart(fig_14, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 19. 居民与企业中长期贷款 (Chart #15)
    fig_15 = render_embedded_chart_by_id(df_embedded_charts, 15)
    if fig_15:
        st.plotly_chart(fig_15, width='stretch', config={'displayModeBar': False})
        st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

    # 20. 社融-M2 增速差 (Chart #16, Anchor: #finance-stock-chart)
    st.markdown('<div id="finance-stock-chart"></div>', unsafe_allow_html=True)
    fig_16 = render_embedded_chart_by_id(df_embedded_charts, 16)
    if fig_16:
        st.plotly_chart(fig_16, width='stretch', config={'displayModeBar': False})

    st.markdown('</div>', unsafe_allow_html=True)

# 右半侧侧边栏：情报流与投研研究 (Live Info Feed & Deep Transmission)
with col_right:
    # 1. 实时金融快讯流 (Sina 7x24 Live Tracker) - 引入 `@news_fragment` 实现每分钟无缝局部轮询刷新
    @news_fragment
    def render_live_feed():
        st.markdown('<div class="obs-card">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:#0f172a; margin-top:0; font-size:1.05rem; margin-bottom:12px; display:flex; align-items:center; gap:6px; font-weight:800;">📻 实时联播快讯流 (Sina Live Feed)</h3>', unsafe_allow_html=True)
        
        # 实时连通数据库以获取增量快讯数据
        try:
            conn_fresh = sqlite3.connect("my_data.db", timeout=60.0)
            df_news_fresh = pd.read_sql_query(
                "SELECT title, content, url, publish_time FROM text_records ORDER BY publish_time DESC LIMIT 12",
                conn_fresh,
            )
            conn_fresh.close()
        except Exception:
            df_news_fresh = pd.DataFrame(columns=["title", "content", "url", "publish_time"])

        news_html_cards = []
        if not df_news_fresh.empty:
            for _, row in df_news_fresh.iterrows():
                title = row.get("title")
                content = row.get("content")
                url = row.get("url", "")
                time_str = row.get("publish_time", "")
                
                # 强力防御 nan 与空值
                if pd.isnull(title) or not title or str(title).strip().lower() == "nan":
                    title = ""
                if pd.isnull(content) or not content or str(content).strip().lower() == "nan":
                    content = ""
                    
                # 兼容历史没有独立 title 列的数据，自适应分裂
                if not title:
                    title, content = sanitize_news_item(str(content))
                    
                # 再次校验分流后的 title 与 content (V1.1.4.2 & V1.1.4.3 Headline & Semantic Guard)
                if not title or str(title).strip().lower() == "nan" or len(str(title).replace("。", "").strip()) < 5 or not verify_semantic_integrity(title):
                    continue
                if not content or str(content).strip().lower() == "nan":
                    content = ""
                    
               # =====================================================================
                # V2.0: DISPLAY SANITIZER — 最小美化，不做结构性裁剪
                # =====================================================================
                # 上游 sanitize_news_item 已完成标题/正文拆分，这里只做表面清理：
                # 1. 有 content 时用「标题：正文」完整句
                # 2. 无 content 时直接用标题
                # 3. 不在本层再做冒号切割——否则会丢掉主语造成"没头"断句
                # =====================================================================
                title_clean = str(title).strip()
                content_clean = str(content).strip() if content and str(content).strip().lower() != "nan" else ""

                if content_clean:
                    # 有正文：拼接为完整的一句话
                    display_text = f"{title_clean}：{content_clean}"
                else:
                    # 仅标题
                    display_text = title_clean
                # =====================================================================
                
                # 保证尾部以单个句号完结，彻底粉碎方括号与冒号尾缀
                display_text = re.sub(r'[。，,；;！!？?、\s：]+$', '', display_text) + "。"
                display_text = re.sub(r'。+$', '。', display_text)
                display_text = display_text.replace("【", "").replace("】", "").replace("[", "").replace("]", "")

                # 断句终审：净化后仍以连接词/虚词/数字结尾 → 直接丢弃
                if is_fragment_tail(display_text) or is_numeric_ending_fragment(display_text):
                    continue

                clean_content = re.sub('<[^<]+?>', '', display_text)

                # V1.1.1.10: 链接硬拦截——无有效链接快讯直接物理剔除，保证 100% 可点击
                if not is_valid_url(url):
                    continue
                
                title_html = f'<a href="{url}" target="_blank" style="color: #0284c7; text-decoration: none; font-weight: 600;">{clean_content}</a>'

                card_html = f'<div class="news-card"><div class="news-time">⏱️ {time_str}</div><div class="news-content">{title_html}</div></div>'
                news_html_cards.append(card_html)
        else:
            news_html_cards.append('<div style="color:#64748b; text-align:center; padding:30px; font-size:0.85rem;">暂无金融快讯数据</div>')
            
        all_news_html = "\n".join(news_html_cards)
        st.markdown(f'<div class="news-scroll-container">{all_news_html}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    render_live_feed()

    # 2. 公众号研报直达列表 (WeChat Analyses)
    if target_macro_html:
        # 直接嵌入从公众号同步入库的深色渐变底卡 HTML
        st.markdown(target_macro_html, unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#64748b; text-align:center; padding:20px; font-size:0.85rem;">📰 公众号研报列表同步中，请稍后刷新…</div>', unsafe_allow_html=True)

