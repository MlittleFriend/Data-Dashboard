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
    # 优先读取 Sheet1；如果文件中没有 Sheet1，则回退读取第一个工作表
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
    该接口免费、无需注册、返回 JSON 格式数据。

    返回：
        list[dict]：每条快讯包含 id、publish_time、content 等字段
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
    print("第二步：抓取最新金融市场热点快讯")
    print("=" * 50)
    news_records = fetch_finance_news(limit=5)

    if news_records:
        print("\n抓取到的前 5 条快讯预览：")
        for idx, record in enumerate(news_records, start=1):
            print(f"{idx}. [{record['publish_time']}] {record['content'][:60]}...")

    import_news_to_db(news_records)

    print("\n全自动化数据导入流程执行完毕！")


if __name__ == "__main__":
    main()
