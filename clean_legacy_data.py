# -*- coding: utf-8 -*-
"""
clean_legacy_data.py | V1.1.1.5 存量垃圾数据全自动清洗脚本
扫描 SQLite 数据库 text_records 表，对历史旧格式记录执行：
1. 内容重新经过 ai_summarize 标准化（40-60 字、方括号实体名词死锁）
2. URL 经过 is_valid_url 前馈审查，非法死链一律置空
"""
import sys

# 将标准输出编码设置为 UTF-8，避免 Windows 终端下中文/Emoji 显示乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import sqlite3
import os
from news_sanitizer import is_valid_url, ai_summarize

DB_FILES = ["my_data.db", "test_my_data.db"]


def clean_db(db_path):
    if not os.path.exists(db_path):
        print(f"[{db_path}] 数据库文件不存在，跳过。")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 确保表存在
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='text_records'"
    )
    if not cursor.fetchone():
        print(f"[{db_path}] 不存在 text_records 表，跳过。")
        conn.close()
        return

    cursor.execute("SELECT rowid, content, url FROM text_records")
    rows = cursor.fetchall()

    updated = 0
    for rowid, content, url in rows:
        content = content or ""
        url = url or ""

        # 强制重新标准化内容
        new_content = ai_summarize(content)

        # 前馈 URL 审查：非法死链置空
        new_url = url.strip() if is_valid_url(url) else ""

        if new_content != content or new_url != url.strip():
            cursor.execute(
                "UPDATE text_records SET content = ?, url = ? WHERE rowid = ?",
                (new_content, new_url, rowid),
            )
            updated += 1

    conn.commit()
    conn.close()
    print(f"[{db_path}] 存量清洗完成：更新 {updated} / {len(rows)} 条记录")


if __name__ == "__main__":
    print("=" * 60)
    print("🧹 V1.1.1.5 存量快讯数据死链与污染标签全自动清洗")
    print("=" * 60)
    for db in DB_FILES:
        clean_db(db)
    print("\n[OK] 存量清洗脚本执行完毕，数据链路已对齐 V1.1.1.5 标准。")
