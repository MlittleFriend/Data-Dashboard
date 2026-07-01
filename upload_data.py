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
    """第一步：同步 Excel 基础数字数据"""
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name="Sheet1")
    except ValueError:
        df = pd.read_excel(EXCEL_FILE, sheet_name=0)

    conn = sqlite3.connect(DB_NAME)
    df.to_sql("sales_records", conn, if_exists="replace", index=False)
    conn.close()
    print("[Database] Excel 数字数据同步成功！")


def fetch_finance_news(limit=5):
    """
    第二步：保持原样抓取新浪财经 7×24 小时公开 API 实时热点快讯
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
        print(f"新浪快讯网络请求失败：{e}")
        return []
    except Exception as e:
        print(f"抓取快讯时出错：{e}")
        return []


def generate_and_save_macro_analysis():
    """
    【本地模板引擎】单独硬编码维护“陈兴团队”公众号最新文章与链接。
    此处全中文输入，标签左侧绝无空格或缩进，彻底杜绝转义黑框 Bug！
    """
    # 1. 维护最新 5 篇文章的标题和真实的微信超链接
    # 未来陈兴团队发布了新文章，你只需要直接在下面修改对应行的文字与 mp.weixin 链接即可！
    link_1 = '<a href="https://mp.weixin.qq.com/s/your_actual_link_1" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">《深度 | 全球储蓄：由过剩到短缺？【华福宏观·陈兴团队】》[查看原文]</a>'
    link_2 = '<a href="https://mp.weixin.qq.com/s/your_actual_link_2" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">《美国核心PCE价格续升——全球经济观察2026年第19期【华福宏观·陈兴团队】》[查看原文]</a>'
    link_3 = '<a href="https://mp.weixin.qq.com/s/your_actual_link_3" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">《中央财政支出提速——2026年5月财政数据解读【陈兴团队·华福宏观】》[查看原文]</a>'
    link_4 = '<a href="https://mp.weixin.qq.com/s/your_actual_link_4" target="_blank" style="color: #0d6efd; text-decoration: underline; font-weight: bold;">《深度 | 英国养老金产品如何设计？——养老金配置系列之二【华福宏观·陈兴团队】》[查看原文]</a>'

    # 2. 拼接生成结构绝对严密、内容靠左顶格的 HTML
    dynamic_html = f'''<div style="background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 12px; padding: 22px; border: 1px solid #dee2e6; font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;">
<h4 style="color:#0d6efd; margin-top:0;">🌐 一、PPI 成本传导链条与全球储蓄演变</h4>
<p style="line-height:1.8; color:#343a40;">
本期上游原材料价格（能源、有色金属）波动通过 PPI 向中游制造业逐步传导。结合陈兴团队发布的重磅研究成果 {link_1}，全球储蓄由过剩走向短缺的格局正对产业链定价产生深远影响。当前价格传导存在时滞与阻力，部分中下游企业利润率仍承压。
</p>
<h4 style="color:#0d6efd;">💧 二、全球通胀压力与央行流动性环境</h4>
<p style="line-height:1.8; color:#343a40;">
海外高频风险方面，最新成果 {link_2} 提示美国核心 PCE 价格持续面临上行扰动。回到国内，央行通过公开市场操作维持流动性<strong>合理充裕</strong>，短端资金利率围绕政策利率窄幅波动。在稳汇率与防资金空转的双重目标下，货币政策更强调精准滴灌。
</p>
<h4 style="color:#0d6efd;">📉 三、财政支出节奏与数据联动观察</h4>
<p style="line-height:1.8; color:#343a40;">
透视国内实体经济基本面，团队在 {link_3} 中指出中央财政支出提速特征。从看板下方 <strong>AA / BB / CC</strong> 三列的联动走势来看，短期波动与中长期趋势产生交织。若后续 BB 与 CC 剪刀差持续收窄，意味着行业内部供需关系正在得到边际改善。
</p>
<div style="background:#e7f3ff; border-left:4px solid #0d6efd; padding:12px 16px; border-radius:8px; margin-top:18px; color:#084298;">
<b>💡 策略提示：</b>下方深度文字解析已精准对接陈兴团队宏观研究大盘。补充养老金行业复盘请点击参阅 {link_4}。看板分析数据更新于：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}。
</div>
</div>'''

    # 3. 单独写入专属的数据库表 macro_analysis
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
        print("[本地渲染引擎] 成功将嵌有微信公众号链接的深度解析报告同步至数据库！")
    except Exception as e:
        print(f"[本地渲染引擎] 数据库写入失败: {e}")


def import_news_to_db(records, table_name="text_records"):
    """将抓取到的新浪快讯写入数据库"""
    if not records:
        print("\n没有获取到任何快讯，跳过写入快讯表。")
        return
    df = pd.DataFrame(records)
    conn = sqlite3.connect(DB_NAME)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    conn.close()
    print(f"[Database] 成功同步 {len(records)} 条实时新浪金融快讯！")


def main():
    print("=" * 50)
    print("第一步：导入 Excel 数字数据")
    print("=" * 50)
    import_excel_to_db()

    print("\n" + "=" * 50)
    print("第二步：全自动抓取新浪快讯 & 本地同步生成宏观深度卡片")
    print("=" * 50)
    
    # 1. 实时抓取新浪 7x24 小时快讯，保持滚动栏常新
    news_records = fetch_finance_news(limit=5)
    import_news_to_db(news_records)
    
    # 2. 独立运行本地模版，组装带超链接的陈兴公众号分析卡片
    generate_and_save_macro_analysis()

    print("\n全自动化数据多流同步流程执行完毕！")


if __name__ == "__main__":
    main()