import sys

# 将标准输出编码设置为 UTF-8，避免 Windows 终端下中文显示乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import sqlite3
import requests
from datetime import datetime

DB_NAME = "my_data.db"
EXCEL_FILE = "26630.xlsx"


def import_excel_to_db():
    """1. 同步 Excel 基础数字数据到数据库"""
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    except ValueError:
        df = pd.read_excel(EXCEL_FILE, sheet_name=0)

    conn = sqlite3.connect(DB_NAME)
    df.to_sql("sales_records", conn, if_exists="replace", index=False)
    conn.close()
    print("[Database] Excel 数字数据同步成功！")


def fetch_wechat_articles():
    """
    2. 【核心修改区】配置华福宏观·陈兴团队最新 5 篇报告的真实链接
    💡 提示：请把下面 url_1 到 url_5 里面的“你的真实微信链接”替换为你从微信电脑端/手机端真实复制出来的 URL 地址。
    """
    url_1 = "https://mp.weixin.qq.com/s/NJq0AEpCbSzP78AwvTDBEQ" 
    url_2 = "https://mp.weixin.qq.com/s/7MYZa-P8amU5OkntRg_rmQ"
    url_3 = "https://mp.weixin.qq.com/s/28vPWqmtoH6TOkXU7LRFEw"
    url_4 = "https://mp.weixin.qq.com/s/tag8klgGoAscSChRCvJdow"  
    url_5 = "https://mp.weixin.qq.com/s/CXtO0LxA0U9gYOFzZ2CH-Q"  

    articles = [
        {
            "id": 1,
            "publish_time": "2026-07-01",
            "content": "深度 | 全球储蓄：由过剩到短缺？【华福宏观·陈兴团队】",
            "url": url_1,
        },
        {
            "id": 2,
            "publish_time": "2026-06-27",
            "content": "美国核心PCE价格续升——全球经济观察2026年第19期【华福宏观·陈兴团队】",
            "url": url_2,
        },
        {
            "id": 3,
            "publish_time": "2026-06-23",
            "content": "中央财政支出提速——2026年5月财政数据解读【陈兴团队·华福宏观】",
            "url": url_3,
        },
        {
            "id": 4,
            "publish_time": "2026-06-21",
            "content": "深度 | 英国养老金产品如何设计？——养老金配置系列之二【华福宏观·陈兴团队】",
            "url": url_4,
        },
        {
            "id": 5,
            "publish_time": "2026-06-20",
            "content": "美国零售销售超预期——全球经济观察2026年第18期【华福宏观·陈兴团队】",
            "url": url_5,
        },
    ]
    return articles


def generate_and_save_macro_analysis():
    """
    3. 纯 Python 本地列表引擎：组装干净、直观的 5 篇报告超链接列表入库
    """
    articles = fetch_wechat_articles()
    if not articles or len(articles) < 5:
        return

    # 构造列表各行带日期的 HTML 超链接超文本（新窗口打开：target="_blank"）
    link_1 = f'<span>📅 {articles[0]["publish_time"]}</span> &nbsp;&nbsp; <a href="{articles[0]["url"]}" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{articles[0]["content"]}</a>'
    link_2 = f'<span>📅 {articles[1]["publish_time"]}</span> &nbsp;&nbsp; <a href="{articles[1]["url"]}" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{articles[1]["content"]}</a>'
    link_3 = f'<span>📅 {articles[2]["publish_time"]}</span> &nbsp;&nbsp; <a href="{articles[2]["url"]}" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{articles[2]["content"]}</a>'
    link_4 = f'<span>📅 {articles[3]["publish_time"]}</span> &nbsp;&nbsp; <a href="{articles[3]["url"]}" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{articles[3]["content"]}</a>'
    link_5 = f'<span>📅 {articles[4]["publish_time"]}</span> &nbsp;&nbsp; <a href="{articles[4]["url"]}" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">{articles[4]["content"]}</a>'

    # 完全顶格的模块化列表容器
    dynamic_html = f'''<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 12px; padding: 22px; border: 1px solid #dee2e6; font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;">
<h4 style="color:#0d6efd; margin-top:0; margin-bottom: 16px;">📰 我们的最新宏观研究成果</h4>
<div style="line-height: 2.2; color: #343a40; font-size: 15px;">
<div style="border-bottom: 1px dashed #dee2e6; padding: 6px 0;">{link_1}</div>
<div style="border-bottom: 1px dashed #dee2e6; padding: 6px 0;">{link_2}</div>
<div style="border-bottom: 1px dashed #dee2e6; padding: 6px 0;">{link_3}</div>
<div style="border-bottom: 1px dashed #dee2e6; padding: 6px 0;">{link_4}</div>
<div style="padding: 6px 0;">{link_5}</div>
</div>
</div>'''

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macro_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                html_text TEXT,
                update_time TEXT
            )
        """)
        cursor.execute("DELETE FROM macro_analysis")
        cursor.execute(
            "INSERT INTO macro_analysis (html_text, update_time) VALUES (?, ?)",
            (dynamic_html, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        print("[本地列表引擎] 5篇最新研究直达列表已成功同步至数据库！")
    except Exception as e:
        print(f"[本地列表引擎] 写入数据库失败: {e}")


def fetch_finance_news(limit=5):
    """4. 实时在线抓取新浪 7x24 快讯以供顶部滚动横幅展现"""
    url = f"https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size={limit}&zhibo_id=152&tag_id=0&dire=1&dpc=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        news_list = response.json().get("result", {}).get("data", {}).get("feed", {}).get("list", [])
        records = []
        for item in news_list[:limit]:
            records.append({
                "id": item.get("id"),
                "publish_time": item.get("create_time"),
                "content": item.get("rich_text", "").strip(),
                "url": item.get("docurl", "").strip(),
                "source": "新浪财经 7×24",
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
        return records
    except Exception as e:
        print(f"新浪快讯网络抓取失败: {e}")
        return []


def import_news_to_db(records, table_name="text_records"):
    """将实时快讯保存到快讯数据库表"""
    if not records:
        return
    df = pd.DataFrame(records)
    conn = sqlite3.connect(DB_NAME)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"[Database] 成功拉取并保存 {len(records)} 条今日新浪金融实时快讯！")


def main():
    print("=" * 50)
    print("🚀 开始执行全自动数据加工处理流水线...")
    print("=" * 50)
    import_excel_to_db()
    
    # 抓取并同步顶部滚动快讯
    news_records = fetch_finance_news(limit=5)
    import_news_to_db(news_records)
    
    # 构建并同步底部手动维护的文章传送门列表
    generate_and_save_macro_analysis()
    
    print("\n[OK] 数据源加工流已全盘就绪！")


if __name__ == "__main__":
    main()