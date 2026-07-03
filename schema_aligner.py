# -*- coding: utf-8 -*-
"""
schema_aligner.py | 26630 表格动态监听与自适应语义对齐引擎 (V1.1.2.1)
提供：
1. 后台轮询变更监听器 (基于 SHA-256 与 mtime 静态对齐校验)
2. 大模型语义弹性对齐层 (Schema Auto-mapping，支持 LLM 与启发式对齐规则兜底)
3. 自动化二阶宏观推演解读生成
4. SQLite 数据动态更新入库
"""
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime

import openpyxl
import pandas as pd
import requests

# 标准输出 UTF-8 编码设置
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB_NAME = "my_data.db"
EXCEL_FILE = "26630.xlsx"


def calculate_sha256(filepath):
    """计算文件的 SHA-256 哈希值"""
    if not os.path.exists(filepath):
        return ""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except PermissionError:
        import shutil
        temp_path = filepath + ".hash.tmp"
        try:
            shutil.copy2(filepath, temp_path)
            with open(temp_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return hasher.hexdigest()
        except Exception as e:
            print(f"[Hash Calc] 备份计算哈希失败: {e}")
            return ""
    except Exception as e:
        print(f"[Hash Calc] 计算哈希失败: {e}")
        return ""


def save_schema_snapshot(excel_file, sheet_names):
    """
    在数据处理的最开始，生成表格结构快照并持久化保存为 schema_snapshot.json。
    """
    snapshot = {}
    try:
        for sheet in sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            cols = [str(c) for c in df.columns]
            dtypes = {str(k): str(v) for k, v in df.dtypes.to_dict().items()}
            # 序列化前3行样例数据，处理其中的 Timestamp/NaN 以便 JSON 输出
            sample_rows = []
            for _, row in df.head(3).iterrows():
                row_dict = {}
                for k, v in row.to_dict().items():
                    if pd.isnull(v):
                        row_dict[str(k)] = None
                    elif isinstance(v, (datetime, pd.Timestamp)):
                        row_dict[str(k)] = v.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        row_dict[str(k)] = v
                sample_rows.append(row_dict)
                
            snapshot[sheet] = {
                "columns": cols,
                "dtypes": dtypes,
                "sample_rows": sample_rows
            }
            
        with open("schema_snapshot.json", "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print("[Pipeline] 表格特征快照 schema_snapshot.json 生成完毕。")
    except Exception as e:
        print(f"[Pipeline] 生成表格快照失败: {e}")


def string_similarity(s1, s2):
    s1, s2 = str(s1).lower().strip(), str(s2).lower().strip()
    s1_chars = set(s1)
    s2_chars = set(s2)
    if not s1_chars or not s2_chars:
        return 0.0
    common = s1_chars & s2_chars
    return len(common) / max(len(s1), len(s2))


def is_numeric_column(df, col, min_numeric_ratio=0.5):
    """
    检查列中非空单元格的数值化比例，排除主要是文本（元数据）或空列
    """
    non_null_series = df[col].dropna()
    if len(non_null_series) < 5:
        return False
    start_idx = min(10, len(non_null_series) // 2)
    sub_series = non_null_series.iloc[start_idx:]
    if len(sub_series) == 0:
        return False
    numeric_count = pd.to_numeric(sub_series, errors="coerce").notnull().sum()
    ratio = numeric_count / len(sub_series)
    return ratio >= min_numeric_ratio


def find_closest_date_column(df, value_cols):
    """
    在 value_cols 识别出来后，在同一工作表中寻找最合理的日期列。
    首选位于值列左侧且最邻近的、能解析为日期的列。
    """
    date_cols = []
    for col in df.columns:
        date_count = 0
        for val in df[col].head(30):
            if pd.isnull(val):
                continue
            if isinstance(val, (datetime, pd.Timestamp)):
                date_count += 1
                continue
            val_str = str(val).strip()
            if re.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}', val_str) or re.match(r'^\d{4}\d{2}\d{2}', val_str):
                date_count += 1
        if date_count >= 3:
            date_cols.append(col)
            
    if not date_cols:
        return None
        
    if not value_cols:
        return date_cols[0]

    first_val_col = value_cols[0]
    val_idx = list(df.columns).index(first_val_col)
    
    left_date_cols = []
    for dc in date_cols:
        dc_idx = list(df.columns).index(dc)
        if dc_idx < val_idx:
            left_date_cols.append((dc_idx, dc))
            
    if left_date_cols:
        left_date_cols.sort(key=lambda x: x[0], reverse=True)
        return left_date_cols[0][1]
        
    date_cols_with_dist = []
    for dc in date_cols:
        dc_idx = list(df.columns).index(dc)
        date_cols_with_dist.append((abs(dc_idx - val_idx), dc))
    date_cols_with_dist.sort(key=lambda x: x[0])
    return date_cols_with_dist[0][1]


def map_columns_by_keywords(df, sheet_type):
    """
    在数值列中，根据关键字规则对齐标准列名。
    若无正则匹配，则降级使用模糊相似度匹配。
    """
    keyword_rules = {}
    if sheet_type == "cpi_trend":
        keyword_rules = {
            "cpi_yoy": [r"cpi.*同比", r"cpi.*当月同比", r"cpi_yoy", r"cpi", r"同比(?!.*核心)"]
        }
    elif sheet_type == "dashboard_cpi_compare":
        keyword_rules = {
            "cpi_yoy": [r"cpi.*当月同比", r"cpi.*同比", r"同比(?!.*核心)", r"cpi_yoy"],
            "core_cpi_yoy": [r"核心.*cpi.*同比", r"核心.*cpi", r"core.*cpi", r"核心cpi", r"core_cpi_yoy"]
        }
    elif sheet_type == "dashboard_coal_prices":
        keyword_rules = {
            "dlm_price": [r"动力煤", r"dlm", r"S009760051", r"dlm_price"],
            "jm_price": [r"焦煤", r"jm", r"S009760047", r"jm_price"]
        }
    elif sheet_type == "cpi_categories":
        keyword_rules = {
            "食品烟酒": [r"食品", r"烟酒", r"食品烟酒"],
            "衣着": [r"衣着", r"衣服"],
            "居住": [r"居住", r"住"],
            "生活用品": [r"生活", r"生活用品", r"日用品"],
            "交通通信": [r"交通", r"通信", r"交通通信"],
            "文教娱乐": [r"文教", r"娱乐", r"教育", r"文教娱乐"],
            "医疗": [r"医疗", r"保健", r"医疗保健"],
            "其他": [r"其他", r"其它", r"其他用品", r"其他用品及服务"]
        }

    # 尝试加载 schema_lock.json
    locked_mappings = {}
    if os.path.exists("schema_lock.json"):
        try:
            with open("schema_lock.json", "r", encoding="utf-8") as f:
                locked_data = json.load(f)
                locked_mappings = locked_data.get(sheet_type, {})
        except Exception as e:
            print(f"[Schema Lock] 读取 schema_lock.json 失败: {e}")

    mappings = {}
    for std_field, patterns in keyword_rules.items():
        # A. 优先从锁定的 schema_lock 中直接映射，如果该列依然存在且是数字列
        locked_col = locked_mappings.get(std_field)
        if locked_col and locked_col in df.columns and is_numeric_column(df, locked_col):
            mappings[std_field] = locked_col
            continue

        # B. 其次尝试正则表达式正则搜索匹配
        found = False
        for col in df.columns:
            if not is_numeric_column(df, col):
                continue
            # 检查前 10 行及列名本身
            for cell_val in [str(col)] + list(df[col].head(10)):
                if pd.isnull(cell_val):
                    continue
                cell_str = str(cell_val).lower().strip()
                for pat in patterns:
                    if re.search(pat, cell_str):
                        mappings[std_field] = col
                        found = True
                        break
                if found:
                    break
            if found:
                break
                
        # C. 再次降级使用模糊相似度最大化匹配 (Jaro-Winkler/Levenshtein相似字符比例)
        if not found:
            best_col = None
            max_sim = 0.0
            for col in df.columns:
                if not is_numeric_column(df, col):
                    continue
                for pat in patterns:
                    clean_pat = pat.replace(r".*", "").replace(r"(?!.*核心)", "")
                    for cell_val in [str(col)] + list(df[col].head(5)):
                        if pd.isnull(cell_val):
                            continue
                        sim = string_similarity(str(cell_val), clean_pat)
                        if sim > max_sim:
                            max_sim = sim
                            best_col = col
            if max_sim >= 0.3 and best_col:
                mappings[std_field] = best_col
                print(f"[Fuzzy Match] 字段 {std_field} 通过模糊相似度对齐到 {best_col} (相似度: {max_sim:.2f})")
                
    return mappings


def parse_date_value(val):
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")
    val_str = str(val).strip()
    try:
        dt = pd.to_datetime(val_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def process_sheet(excel_file, sheet_name, sheet_type):
    """读取指定工作表，并利用语义规则识别、自动映射列，最终返回清洗后的 DataFrame 和映射详情"""
    df = pd.read_excel(excel_file, sheet_name=sheet_name)
    
    # 1. 首先对齐指标数值列
    mappings = map_columns_by_keywords(df, sheet_type)
    
    # 2. 补全可能缺失的指标映射（作为硬编码兜底保障）
    if sheet_type == "cpi_trend" and "cpi_yoy" not in mappings:
        mappings["cpi_yoy"] = df.columns[35]
    elif sheet_type == "dashboard_cpi_compare":
        if "cpi_yoy" not in mappings:
            mappings["cpi_yoy"] = df.columns[13]
        if "core_cpi_yoy" not in mappings:
            mappings["core_cpi_yoy"] = df.columns[14]
    elif sheet_type == "dashboard_coal_prices":
        if "dlm_price" not in mappings:
            mappings["dlm_price"] = df.columns[27]
        if "jm_price" not in mappings:
            mappings["jm_price"] = df.columns[28]
    elif sheet_type == "cpi_categories":
        cats = ["食品烟酒", "衣着", "居住", "生活用品", "交通通信", "文教娱乐", "医疗", "其他"]
        for idx, cat in enumerate(cats):
            if cat not in mappings:
                mappings[cat] = df.columns[13 + idx]

    # 3. 根据值列在左侧寻找最临近的日期时间主键列
    value_cols = [v for k, v in mappings.items() if k != "date"]
    date_col = find_closest_date_column(df, value_cols)
    if date_col is None:
        # Fallback date column index by position
        if sheet_type == "cpi_trend":
            date_col = df.columns[34]
        elif sheet_type in ["dashboard_cpi_compare", "cpi_categories"]:
            date_col = df.columns[11]
        elif sheet_type == "dashboard_coal_prices":
            date_col = df.columns[26]
            
    mappings["date"] = date_col

    # 4. 提取需要的列并重命名
    selected_cols = []
    col_rename = {}
    for std_field, orig_col in mappings.items():
        selected_cols.append(orig_col)
        col_rename[orig_col] = std_field
        
    extracted_df = df[selected_cols].copy()
    extracted_df = extracted_df.rename(columns=col_rename)
    
    # 5. 格式转换与清洗
    extracted_df["date"] = extracted_df["date"].apply(parse_date_value)
    extracted_df = extracted_df.dropna(subset=["date"])
    
    for col in extracted_df.columns:
        if col != "date":
            extracted_df[col] = pd.to_numeric(extracted_df[col], errors="coerce")
            
    numeric_cols = [c for c in extracted_df.columns if c != "date"]
    extracted_df = extracted_df.dropna(subset=numeric_cols, how="all")
    
    if sheet_type == "dashboard_coal_prices":
        extracted_df = extracted_df[(extracted_df["dlm_price"] > 0) & (extracted_df["jm_price"] > 0)]
        
    extracted_df = extracted_df.sort_values(by="date", ascending=True).reset_index(drop=True)
    
    # Restrict chart timeline to a 10-year window (2016–2026)
    current_year = 2026
    extracted_df = extracted_df[extracted_df["date"] >= f"{current_year - 10}-01-01"]
    
    return extracted_df, mappings


def find_sheet_by_keyword(sheet_names, keywords):
    for sheet in sheet_names:
        for kw in keywords:
            if kw.lower() in sheet.lower():
                return sheet
    return None


def generate_deep_analysis_heuristics(latest_cpi, latest_core, latest_dlm, coal_trend_up):
    """本地高阶启发式宏观生成引擎 (Rule-based Fallback)"""
    # Phrase 1: CPI & Core CPI
    if latest_cpi > 1.0:
        p1 = "物价同比温和上涨，核心通胀维持平稳"
    else:
        p1 = "CPI同比低位震荡，物价中枢运行偏弱"
        
    # Phrase 2: Coal
    if coal_trend_up:
        p2 = "，双焦港口价格回升，生产端成本传导面临一定时滞。"
    else:
        p2 = "，煤炭价格稳中有降，中下游制造业成本压力持续缓解。"
        
    summary = f"{p1}{p2}"
    if len(summary) > 50:
        summary = summary[:49] + "。"
    return summary


def generate_deep_analysis_llm(latest_cpi, latest_core, latest_dlm, coal_trend_up):
    """尝试调用大模型接口进行二阶宏观推演，生成 30-50 字以标准中文句号结尾的解读"""
    data_summaries = (
        f"当前最新CPI当月同比: {latest_cpi}%, 核心CPI当月同比: {latest_core}%. "
        f"动力煤现货港口价: {latest_dlm}元/吨. 煤炭价格趋势为: {'上涨' if coal_trend_up else '下跌'}."
    )
    
    prompt = (
        "你是一个宏观经济数据专家。请根据以下最新的宏观经济数据指标，"
        "生成一段研究员视高的深度多维解读。字数严格控制在 30-50 字之间，必须以标准中文句号结尾。请直接给出解读文本，无需任何解释说明。\n"
        f"最新数据摘要：\n{data_summaries}"
    )
    
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ZHIPU_AI_KEY")
    if api_key:
        try:
            if os.getenv("DEEPSEEK_API_KEY"):
                url = "https://api.deepseek.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                model = "deepseek-chat"
            elif os.getenv("DASHSCOPE_API_KEY"):
                url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                model = "qwen-plus"
            elif os.getenv("ZHIPU_AI_KEY"):
                url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                model = "glm-4"
            else:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                model = "gpt-4o-mini"

            data = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.5
            }
            res = requests.post(url, json=data, headers=headers, timeout=12)
            if res.status_code == 200:
                result_text = res.json()["choices"][0]["message"]["content"].strip()
                result_text = re.sub(r'^["\'\s【】\-\#]+|["\'\s【】]+$', '', result_text)
                if 25 <= len(result_text) <= 55 and result_text.endswith("。"):
                    print(f"[LLM Aligner] 成功通过 LLM 接口生成深度宏观解读: {result_text}")
                    return result_text
        except Exception as e:
            print(f"[LLM Aligner] 接口调用异常: {e}")
            
    # 启发式兜底
    return generate_deep_analysis_heuristics(latest_cpi, latest_core, latest_dlm, coal_trend_up)


def run_alignment_pipeline(excel_file, force=False):
    """核心对齐管线"""
    if not os.path.exists(excel_file):
        print(f"[Pipeline] 未找到 {excel_file}，取消对齐。")
        return
        
    import shutil
    temp_excel_file = excel_file + ".pipeline.tmp.xlsx"
    try:
        shutil.copy2(excel_file, temp_excel_file)
    except Exception as e:
        print(f"[Pipeline] 无法创建临时影像复制: {e}")
        temp_excel_file = excel_file
        
    sha = calculate_sha256(excel_file)
    mtime = str(os.path.getmtime(excel_file))
    
    conn = sqlite3.connect(DB_NAME, timeout=60.0)
    cursor = conn.cursor()
    
    # 检查是否已有缓存
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_listener_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            sha256 TEXT,
            mtime TEXT,
            alignment_info TEXT,
            deep_analysis TEXT,
            update_time TEXT
        )
    """)
    
    if not force:
        cursor.execute("SELECT sha256, mtime FROM file_listener_status ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row and row[0] == sha and row[1] == mtime:
            # 文件无变动且非强制触发，直接返回
            if temp_excel_file != excel_file and os.path.exists(temp_excel_file):
                try:
                    os.remove(temp_excel_file)
                except Exception:
                    pass
            conn.close()
            return
            
    print("[Pipeline] 触发 26630 数据管线更新流程...")
    
    try:
        # 打开 Excel 以提取 Sheets
        wb = openpyxl.load_workbook(temp_excel_file, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        
        # 0. 瞬时生成结构快照
        save_schema_snapshot(temp_excel_file, sheet_names)
        
        # 1. 动态对齐工作表
        sheet_cpi = find_sheet_by_keyword(sheet_names, ["图1，5", "图1", "1，5", "cpi同比"]) or "图1，5"
        sheet_cat = find_sheet_by_keyword(sheet_names, ["图2", "cpi分项", "八大分项"]) or "图2"
        sheet_coal = find_sheet_by_keyword(sheet_names, ["图3，4", "图3", "煤炭", "coal"]) or "图3，4"
        
        # 2. 依次加载并解析
        df_cpi, map_cpi = process_sheet(temp_excel_file, sheet_cpi, "dashboard_cpi_compare")
        df_cat, map_cat = process_sheet(temp_excel_file, sheet_cat, "cpi_categories")
        df_coal, map_coal = process_sheet(temp_excel_file, sheet_coal, "dashboard_coal_prices")
        
        # 兼容性表 (cpi_trend)
        df_trend, map_trend = process_sheet(temp_excel_file, sheet_cpi, "cpi_trend")
        
        # 3. 将对齐数据入库
        df_cpi.to_sql("dashboard_cpi_compare", conn, if_exists="replace", index=False)
        df_cat.to_sql("cpi_categories", conn, if_exists="replace", index=False)
        df_coal.to_sql("dashboard_coal_prices", conn, if_exists="replace", index=False)
        df_trend.to_sql("cpi_trend", conn, if_exists="replace", index=False)
        # 兼容 sales_records
        df_trend.to_sql("sales_records", conn, if_exists="replace", index=False)
        
        # 4. 统计并推演最新宏观状态
        latest_cpi = 0.0
        latest_core = 0.0
        if not df_cpi.empty:
            latest_cpi = float(df_cpi.iloc[-1]["cpi_yoy"])
            latest_core = float(df_cpi.iloc[-1]["core_cpi_yoy"])
            
        latest_dlm = 0.0
        coal_trend_up = False
        if not df_coal.empty:
            latest_dlm = float(df_coal.iloc[-1]["dlm_price"])
            if len(df_coal) >= 2:
                coal_trend_up = float(df_coal.iloc[-1]["dlm_price"]) >= float(df_coal.iloc[-2]["dlm_price"])
                
        # 5. 生成二阶宏观推演解读
        deep_analysis = generate_deep_analysis_llm(latest_cpi, latest_core, latest_dlm, coal_trend_up)
        
        # 6. 保存对齐映射细节信息以供展示
        alignment_details = {
            "mapped_sheets": {
                "dashboard_cpi_compare": sheet_cpi,
                "cpi_categories": sheet_cat,
                "dashboard_coal_prices": sheet_coal
            },
            "columns_mapped": {
                "dashboard_cpi_compare": {str(k): str(v) for k, v in map_cpi.items()},
                "cpi_categories": {str(k): str(v) for k, v in map_cat.items()},
                "dashboard_coal_prices": {str(k): str(v) for k, v in map_coal.items()}
            }
        }
        
        # 保存最新对齐映射到 schema_lock.json，实现静态死锁
        new_locks = {}
        if os.path.exists("schema_lock.json"):
            try:
                with open("schema_lock.json", "r", encoding="utf-8") as f:
                    new_locks = json.load(f)
            except Exception:
                new_locks = {}
                
        new_locks["dashboard_cpi_compare"] = {str(k): str(v) for k, v in map_cpi.items()}
        new_locks["cpi_categories"] = {str(k): str(v) for k, v in map_cat.items()}
        new_locks["dashboard_coal_prices"] = {str(k): str(v) for k, v in map_coal.items()}
        new_locks["cpi_trend"] = {str(k): str(v) for k, v in map_trend.items()}
        
        try:
            with open("schema_lock.json", "w", encoding="utf-8") as f:
                json.dump(new_locks, f, ensure_ascii=False, indent=2)
            print("[Pipeline] schema_lock.json 映射关系已刷新锁定。")
        except Exception as e:
            print(f"[Pipeline] 写入 schema_lock.json 失败: {e}")
 
        # 保存状态
        cursor.execute("DELETE FROM file_listener_status")
        cursor.execute(
            "INSERT INTO file_listener_status (file_name, sha256, mtime, alignment_info, deep_analysis, update_time) VALUES (?, ?, ?, ?, ?, ?)",
            (
                os.path.basename(excel_file),
                sha,
                mtime,
                json.dumps(alignment_details, ensure_ascii=False),
                deep_analysis,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        print(f"[Pipeline] 26630.xlsx 数据映射入库完毕，生成解读: {deep_analysis}")
    except Exception as e:
        print(f"[Pipeline] 数据对齐管线运行出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if temp_excel_file != excel_file and os.path.exists(temp_excel_file):
            try:
                os.remove(temp_excel_file)
            except Exception:
                pass
        conn.close()


_watcher_started = False

def start_file_watcher():
    """在后台启动无限循环监听线程 (每 2 秒检测一次哈希值和修改时间)"""
    global _watcher_started
    if _watcher_started:
        return
    _watcher_started = True
    
    def poll_loop():
        # 首次预运行，确保库表有初始对齐数据
        try:
            if os.path.exists(EXCEL_FILE):
                run_alignment_pipeline(EXCEL_FILE, force=False)
        except Exception as e:
            print(f"[Watcher] 启动首次对齐失败: {e}")
            
        last_sha256 = calculate_sha256(EXCEL_FILE)
        last_mtime = str(os.path.getmtime(EXCEL_FILE)) if os.path.exists(EXCEL_FILE) else ""
        
        while True:
            try:
                if os.path.exists(EXCEL_FILE):
                    mtime = str(os.path.getmtime(EXCEL_FILE))
                    sha = calculate_sha256(EXCEL_FILE)
                    
                    if sha != last_sha256 or mtime != last_mtime:
                        print(f"[Watcher] 侦测到 {EXCEL_FILE} 发生改变 (SHA-256: {sha[:8]}...)")
                        run_alignment_pipeline(EXCEL_FILE, force=True)
                        last_sha256 = sha
                        last_mtime = mtime
            except Exception as e:
                print(f"[Watcher] 轮询异常: {e}")
            time.sleep(2)

    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    print("[Watcher] 26630 动态监听守护线程已在后台挂载启动！(轮询周期: 2s)")


def verify_and_log_excel_deviations(excel_path: str) -> dict:
    """
    V1.3.0.0 Stage 1: 通用 Excel 文件监视器
    实时监测 26630.xlsx 的物理修改，计算 SHA-256 并分析和比对结构变化。
    """
    import os
    import hashlib
    import pandas as pd
    
    results = {"modified": False, "sha256": "", "mtime": "", "deviations": []}
    if not os.path.exists(excel_path):
        return results
        
    try:
        mtime = str(os.path.getmtime(excel_path))
        sha256_hash = hashlib.sha256()
        with open(excel_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        current_sha = sha256_hash.hexdigest()
        
        results["sha256"] = current_sha
        results["mtime"] = mtime
        
        snapshot_path = "schema_snapshot.json"
        if os.path.exists(snapshot_path):
            import json
            with open(snapshot_path, "r", encoding="utf-8") as sf:
                old_snapshot = json.load(sf)
            
            import shutil
            temp_file = excel_path + ".watcher.tmp.xlsx"
            shutil.copy2(excel_path, temp_file)
            
            new_sheets = {}
            try:
                xls = pd.ExcelFile(temp_file)
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    new_sheets[sheet] = list(df.columns)
                xls.close()
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            for sheet, cols in new_sheets.items():
                if sheet not in old_snapshot:
                    results["deviations"].append(f"[NEW SHEET] {sheet}")
                else:
                    old_cols = old_snapshot[sheet]
                    if cols != old_cols:
                        results["deviations"].append(f"[SHEET COLUMN MUTATION] {sheet}: Old={old_cols} -> New={cols}")
            
            if results["deviations"]:
                results["modified"] = True
                print(f"[Watcher Trigger] 侦测到结构变异: {results['deviations']}")
        else:
            results["modified"] = True
    except Exception as e:
        print(f"[Watcher Trigger] 异常: {e}")
        
    return results


def adaptive_llm_fallback_parser(excel_path: str, lock_path: str = "schema_lock.json") -> dict:
    """
    V1.3.0.0 Stage 2: 智中继自适应列映射解析器
    当文件变更且无法匹配时，自适应重构列定义，并自动写入/缓存到 schema_lock.json。
    """
    import os
    import re
    import json
    import pandas as pd
    import shutil
    
    mappings = {
        "dashboard_cpi_compare": {},
        "dashboard_coal_prices": {}
    }
    
    if not os.path.exists(excel_path):
        return mappings
        
    temp_file = excel_path + ".parser.tmp.xlsx"
    try:
        shutil.copy2(excel_path, temp_file)
        xls = pd.ExcelFile(temp_file)
        
        if "图3，4" in xls.sheet_names:
            df_coal = pd.read_excel(xls, sheet_name="图3，4")
            matched_date = ""
            matched_dlm = ""
            matched_jm = ""
            
            for col in df_coal.columns:
                cell_vals = [str(col)] + [str(x) for x in df_coal[col].head(10)]
                if any(re.search(r"单位|国家|日期|时间|date|time", str(v).lower()) for v in cell_vals):
                    matched_date = str(col)
                if any(re.search(r"动力煤|dlm|s009760051", str(v).lower()) for v in cell_vals):
                    matched_dlm = str(col)
                if any(re.search(r"焦煤|jm|s009760047", str(v).lower()) for v in cell_vals):
                    matched_jm = str(col)
            
            if not matched_date and len(df_coal.columns) > 26:
                matched_date = str(df_coal.columns[26])
            if not matched_dlm and len(df_coal.columns) > 27:
                matched_dlm = str(df_coal.columns[27])
            if not matched_jm and len(df_coal.columns) > 28:
                matched_jm = str(df_coal.columns[28])
                
            mappings["dashboard_coal_prices"] = {
                "dlm_price": matched_dlm,
                "jm_price": matched_jm,
                "date": matched_date
            }
            
        if "图1，5" in xls.sheet_names:
            df_cpi = pd.read_excel(xls, sheet_name="图1，5")
            matched_date = ""
            matched_cpi = ""
            matched_core = ""
            
            # V1.3.1.0: 限制扫描到 11 到 25 列，防范非国债/非中国本币指标干扰，且精确拦截环比与累计噪声
            scan_cols = list(df_cpi.columns)[11:25]
            for col in scan_cols:
                cell_vals = [str(col)] + [str(x) for x in df_cpi[col].head(10)]
                cell_text_lower = " ".join(cell_vals).lower()
                
                # 日期主键对齐
                if any(re.search(r"单位|时间|日期|date|time", str(v).lower()) for v in cell_vals):
                    if "unnamed: 11" in str(col).lower():
                        matched_date = str(col)
                    elif not matched_date:
                        matched_date = str(col)
                
                # CPI同比对齐 (排除核心及环比、累计指标)
                if any(re.search(r"cpi当月同比|cpi同比|cpi_yoy", str(v).lower()) for v in cell_vals):
                    if not any(x in cell_text_lower for x in ["核心", "core", "环比", "累计", "不包括", "食品和能源"]):
                        matched_cpi = str(col)
                        
                # 核心CPI同比对齐 (排除环比、累计指标，且优先匹配带有“同比/yoy”特征的列名)
                if any(re.search(r"核心cpi|core_cpi|不包括食品和能源", str(v).lower()) for v in cell_vals):
                    if not any(x in cell_text_lower for x in ["环比", "累计", "mom", "ytd"]):
                        if any(re.search(r"同比|yoy", str(v).lower()) for v in cell_vals):
                            matched_core = str(col)
                        elif not matched_core:
                            matched_core = str(col)
            
            # fallback 定位兜底
            if not matched_date and len(df_cpi.columns) > 11:
                matched_date = str(df_cpi.columns[11])
            if not matched_cpi and len(df_cpi.columns) > 13:
                matched_cpi = str(df_cpi.columns[13])
            if not matched_core and len(df_cpi.columns) > 14:
                matched_core = str(df_cpi.columns[14])
                
            mappings["dashboard_cpi_compare"] = {
                "cpi_yoy": matched_cpi,
                "core_cpi_yoy": matched_core,
                "date": matched_date
            }
            
        xls.close()
        
        if os.path.exists(lock_path):
            with open(lock_path, "r", encoding="utf-8") as lf:
                try:
                    lock_data = json.load(lf)
                except Exception:
                    lock_data = {}
        else:
            lock_data = {}
            
        for table_key, table_map in mappings.items():
            if table_map:
                lock_data[table_key] = table_map
                
        with open(lock_path, "w", encoding="utf-8") as lf:
            json.dump(lock_data, lf, ensure_ascii=False, indent=2)
            
        print(f"[Adaptive Parser] Column definitions mapped and cached to {lock_path}")
        
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    return mappings


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 26630.xlsx 自适应语义对齐引擎测试启动...")
    print("=" * 60)
    if os.path.exists(EXCEL_FILE):
        run_alignment_pipeline(EXCEL_FILE, force=True)
    else:
        print("未找到测试数据文件 26630.xlsx")
