# -*- coding: utf-8 -*-
"""
pipeline_tools.py | 自定义工具集 - 自动化数据清洗与状态监听 Skill (V1.1.2.9)
"""
import hashlib
import os
import re


def calculate_file_hash(filepath: str) -> str:
    """
    计算并返回指定物理文件的 SHA-256 哈希字符串，用于状态变动监听。
    
    Args:
        filepath: 目标文件的绝对路径或相对路径。
        
    Returns:
        SHA-256 哈希字符，如果文件不存在则返回空字符串。
    """
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"[Skill calculate_file_hash] 异常: {e}")
        return ""


def clean_news_brackets_and_nan(title: str, content: str) -> tuple[str, str]:
    """
    清洗原始的标题与正文字段，物理清除所有的 nan 幽灵和残留方括号。
    
    Args:
        title: 新闻原始标题。
        content: 新闻正文内容。
        
    Returns:
        清洗后的元组 (title, content)。
    """
    t_clean = str(title).strip()
    c_clean = str(content).strip()
    
    if not t_clean or t_clean.lower() == "nan":
        t_clean = ""
    if not c_clean or c_clean.lower() == "nan":
        c_clean = ""
        
    # 清理所有的括号
    t_clean = t_clean.replace("【", "").replace("】", "").replace("[", "").replace("]", "").replace("（", "").replace("）", "")
    c_clean = c_clean.replace("【", "").replace("】", "").replace("[", "").replace("]", "")
    
    return t_clean, c_clean


def process_news_length_rule(title: str, body: str) -> tuple[str, str]:
    """
    依据标题长度硬断言执行前馈拦截分流控制（字数安全熔断控制）：
    - 标题 > 10 字：触发总结熔断机制。只保留并写出原标题，末尾追加句号，content 留空。
    - 标题 <= 10 字：拼接格式为：{原标题}：{核心简讯}，总字数严格死锁在 40 - 60 字之间。
    
    Args:
        title: 干净的原始标题。
        body: 干净的正文段落。
        
    Returns:
        格式化后的元组 (final_title, final_content)。
    """
    title, body = clean_news_brackets_and_nan(title, body)
    if not title:
        title = "全球要闻"
        
    if len(title) > 10:
        # 条件 A: 标题 > 10 字
        title_text = re.sub(r'[。，,；;！!？?、\s：]+$', '', title)
        if len(title_text) > 58:
            title_text = title_text[:55] + "..."
        title_text = title_text + "。"
        return title_text, ""
        
    # 条件 B: 标题 <= 10 字
    max_body_len = 58 - len(title)
    clauses = [c.strip() for c in re.split(r'[，,；;。！!？?、]', body) if c.strip()]
    accumulated_body = ""
    for c in clauses:
        separator = "，" if accumulated_body else ""
        test_body = accumulated_body + separator + c
        if len(test_body) <= max_body_len:
            accumulated_body = test_body
        else:
            break
            
    # 截断与不完整清理
    if not accumulated_body and clauses:
        accumulated_body = clauses[0][:max_body_len]
        
    # 最小填充
    combined_len = len(title) + 2 + len(accumulated_body)
    if combined_len < 40:
        tail = "，观察哨对此持续保持高频监测与深度跟踪"
        needed = 40 - combined_len
        accumulated_body = accumulated_body + tail[:needed+5]
        
    # 再次卡字数
    combined_len = len(title) + 2 + len(accumulated_body)
    if combined_len > 60:
        overflow = combined_len - 60
        accumulated_body = accumulated_body[:-overflow]
        
    # 句号完结
    accumulated_body = re.sub(r'[。，,；;！!？?、\s：]+$', '', accumulated_body) + "。"
    accumulated_body = re.sub(r'。+$', '。', accumulated_body)
    
    return title.strip(), accumulated_body.strip()
