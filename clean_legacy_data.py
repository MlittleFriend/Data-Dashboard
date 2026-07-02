# -*- coding: utf-8 -*-
"""
clean_legacy_data.py | V1.1.2 存量数据全自动清洗脚本
扫描 SQLite 数据库 text_records 表，对历史旧格式记录执行：
1. 内容重新经过 ai_summarize 标准化（40-60 字、方括号实体名词死锁并保证唯一性）
2. URL 经过 is_valid_url 前馈审查，非法无链快讯物理删除抹除
"""
import sys

# 将标准输出编码设置为 UTF-8，避免 Windows 终端下中文/Emoji 显示乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import sqlite3

from news_sanitizer import ai_summarize, is_valid_url

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

    deleted = 0
    updated = 0
    for rowid, content, url in rows:
        content = content or ""
        url = url or ""

        # 链接硬拦截：非法/无有效链接直接物理删除，防止污染大屏
        if not is_valid_url(url):
            cursor.execute("DELETE FROM text_records WHERE rowid = ?", (rowid,))
            deleted += 1
            continue

        # 强制重新标准化内容
        new_content = ai_summarize(content)

        # 强制在最开头保留唯一一套【】方括号，剥离其余所有【】与[]
        if new_content.startswith("【"):
            parts = new_content.split("】", 1)
            if len(parts) > 1:
                prefix = parts[0] + "】"
                body = parts[1].replace("【", "").replace("】", "").replace("[", "").replace("]", "")
                new_content = prefix + body

        if new_content != content:
            cursor.execute(
                "UPDATE text_records SET content = ? WHERE rowid = ?",
                (new_content, rowid),
            )
            updated += 1

    conn.commit()
    conn.close()
    print(f"[{db_path}] 存量清洗完成：物理删除无链记录 {deleted} 条，更新 {updated} / {len(rows)} 条记录")


if __name__ == "__main__":
    print("=" * 60)
    print("🧹 V1.1.2 存量快讯数据死链物理抹除与唯一方括号强制约束")
    print("=" * 60)
    for db in DB_FILES:
        clean_db(db)
    print("\n[OK] 存量清洗脚本执行完毕，数据链路已对齐 V1.1.2 标准。")
