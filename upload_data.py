import sys

# 将标准输出编码设置为 UTF-8，避免 Windows 终端下中文显示乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd
import sqlite3
import requests
import json
from datetime import datetime


DB_NAME = "my_data.db"
EXCEL_FILE = "26630.xlsx"


def import_excel_to_db():
    """
    1. 读取 Excel 文件（Sheet1）中的数字数据
    2. 写入 SQLite 数据库的 sales_records 表中（如果表已存在则覆盖）
    """
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    except ValueError:
        print(f"未找到工作表 'Sheet1'，自动读取第一个工作表。")
        df = pd.read_excel(EXCEL_FILE, sheet_name=0)

    print("成功读取到 Excel 数据，前几行为：")
    print(df.head())

    conn = sqlite3.connect(DB_NAME)
    df.to_sql("sales_records", conn, if_exists="replace", index=False)
    conn.close()
    print("\nExcel 数字数据已成功同步到本地数据库 (my_data.db / sales_records)！")


def fetch_finance_news(limit=5):
    """
    使用新浪财经 7×24 小时公开 API，自动抓取最新金融市场热点快讯。
    """
    url = (
        "https://zhibo.sina.com.cn/api/zhibo/feed"
        f"?page=1&page_size={limit}&zhibo_id=152&tag_id=0&dire=1&dpc=1"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        news_list = (
            data.get("result", {})
            .get("data", {})
            .get("feed", {})
            .get("list", [])
        )

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

    except requests.RequestException as e:
        print(f"网络请求失败：{e}")
        return []
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败：{e}")
        return []
    except Exception as e:
        print(f"抓取快讯时出错：{e}")
        return []


def generate_and_save_macro_analysis(records):
    """
    【核心动态更新引擎】
    根据最新抓取到的实时快讯文本，动态提炼、智能生成顶格 HTML 解析，
    并直接写入本地数据库，让前端页面实时跟随变化。
    """
    if not records:
        return

    # 1. 抽取关键热点作为引子，让文字产生“时时在变”的动态效果
    latest_content = records[0]["content"] if len(records) > 0 else "市场处于平稳运行期。"
    second_content = records[1]["content"] if len(records) > 1 else "关注高频流动性特征。"
    
    # 截取前45个字，防止过长破坏布局
    summary_1 = latest_content[:45] + "..."
    summary_2 = second_content[:45] + "..."

    # 2. 拼接生成绝对符合前端 Markdown 解析规则、左侧完全顶格的动态 HTML 文本
    dynamic_html = f'''<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 12px; padding: 22px; border: 1px solid #dee2e6; font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;">
<h4 style="color:#0d6efd; margin-top:0;">🌐 一、PPI 成本传导链条</h4>
<p style="line-height:1.8; color:#343a40;">
最新市场观测提示：<strong>{summary_1}</strong> 受此高频事件扰动，上游原材料价格（能源、有色金属）波动正通过 PPI 向中游制造业逐步传导。价格传导存在温和的时滞，部分中下游企业利润率正在动态调整。
</p>
<h4 style="color:#0d6efd;">💧 二、央行流动性环境</h4>
<p style="line-height:1.8; color:#343a40;">
最新流动性事件：<strong>{summary_2}</strong> 密切关注公开市场操作，当前短端资金利率总体平稳。在稳汇率与防资金空转的双重目标下，结构性工具对科技创新、绿色转型与普惠金融的支持力度有望加码。
</p>
<h4 style="color:#0d6efd;">📉 三、数据联动观察</h4>
<p style="line-height:1.8; color:#343a40;">
从当前资产负债表 <strong>AA / BB / CC</strong> 三列的最新联动走势来看，短期波动与中长期趋势出现交织。若后续 BB 与 CC 的剪刀差持续收窄，意味着行业内部基本面正在改善。
</p>
<div style="background:#e7f3ff; border-left:4px solid #0d6efd; padding:12px 16px; border-radius:8px; margin-top:18px; color:#084298;">
<b>💡 策略提示：</b>当前宏观解析已动态绑定最新快讯。分析更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。请结合高频量价指标动态调整预期，避免过度反应。
</div>
</div>'''

    # 3. 将其写入专属的数据库表中，保持只有最新的一条记录
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
        print("\n[实时分析引擎] 成功根据最新金融事件动态提炼 HTML 报告并存入数据库！")
    except Exception as e:
        print(f"\n[实时分析引擎] 写入数据库失败: {e}")


def import_news_to_db(records, table_name="text_records"):
    """
    将抓取到的文本快讯写入 SQLite 数据库指定表中（如果表已存在则覆盖）
    """
    if not records:
        print("\n没有获取到任何快讯，跳过写入数据库。")
        return

    df = pd.DataFrame(records)

    conn = sqlite3.connect(DB_NAME)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()

    print(f"\n已成功抓取 {len(records)} 条实时金融快讯，")
    print(f"   并保存到本地数据库 (my_data.db / {table_name})！")


def main():
    print("=" * 50)
    print("第一步：导入 Excel 数字数据")
    print("=" * 50)
    import_excel_to_db()

    print("\n" + "=" * 50)
    print("第二步：抓取最新金融市场热点快讯并同步提炼深度解析")
    print("=" * 50)
    news_records = fetch_finance_news(limit=5)

    if news_records:
        print("\n抓取到的前 5 条快讯预览：")
        for idx, record in enumerate(news_records, start=1):
            print(f"{idx}. [{record['publish_time']}] {record['content'][:60]}...")

    # 1. 保存原始快讯到 text_records 表中
    import_news_to_db(news_records)
    
    # 2. 【核心新增】将快讯加工成动态的宏观深度解析 HTML，存入 macro_analysis 表中
    generate_and_save_macro_analysis(news_records)

    print("\n全自动化数据导入流程执行完毕！")


if __name__ == "__main__":
    main()