# -*- coding: utf-8 -*-
"""
news_sanitizer.py | 实时快讯终极清洗层 (V1.1.1.11)
负责：URL 前馈合法性审查、方括号实体名词死锁、AI 定长摘要。
本模块保持零 Streamlit 依赖，可被 App.py 与离线清洗脚本共同引用。
"""
import re


# ---------------------------------------------------------------------------
# STEP 1: URL 前馈合法性审查 — 彻底消灭灰色/空白死链
# ---------------------------------------------------------------------------
def is_valid_url(url_val):
    """
    对 href 字段执行精确分流审查：
    ✅ 以 http:// 或 https:// 开头的真实外网链接 → 合法（保留 <a> 高亮态）
    ❌ 空链、javascript 跳转、常见空占位符 → 非法（DOM 降级为纯文本）
    避免上一版过度校验导致正常新闻链接被误清洗。
    """
    if not url_val or not isinstance(url_val, str):
        return False

    url_val = url_val.strip()
    if not url_val:
        return False

    lowered = url_val.lower()

    # 1. 拦截 js 跳转与常见空占位符
    if "javascript:" in lowered or "void(0)" in lowered:
        return False

    empty_placeholders = {
        "", "#", "##", "###", "null", "none", "undefined", "about:blank",
        "http://#", "https://#", "http://", "https://",
        "http://null", "https://null",
        "http://none", "https://none",
        "http://undefined", "https://undefined",
        "http://javascript:void(0)", "https://javascript:void(0)",
        "http://about:blank", "https://about:blank",
    }
    if lowered in empty_placeholders:
        return False

    # 2. 仅接受可直接跳转的 http/https 真实协议
    if not (url_val.startswith("http://") or url_val.startswith("https://")):
        return False

    return True


# ---------------------------------------------------------------------------
# STEP 2: 方括号实体名词死锁 — 强制名词、禁止动词/数字/指标因子
# ---------------------------------------------------------------------------
def clean_entity_candidate(cand):
    """
    对候选实体进行死锁式前馈清洗，确保方括号内部为结构闭环的
    实体名称、行业、地区或国家短名词，长度 2-8 字。
    坚决拦截动词、状态描述、数字修饰、指标因子等污染。
    """
    if not cand:
        return ""

    cand = str(cand).strip()

    # 剥离头尾标点、括号与空白噪声
    cand = re.sub(r'^[：，,。；;！!？?、\s【】\[\]\(\)\（\）\-\—]+', '', cand)
    cand = re.sub(r'[：，,。；;！!？?、\s【】\[\]\(\)\（\）\-\—]+$', '', cand)

    if not cand:
        return ""

    # 1. 循环剥离前置数字/时间/量词修饰（层叠情况可多次处理）
    numeric_prefixes = [
        r'^\d+年期', r'^\d+年', r'^\d+月', r'^\d+日', r'^\d+周',
        r'^第?\d+季度', r'^第?\d+月', r'^第?\d+周',
        r'^\d+个基点', r'^\d+个百分点', r'^\d+个点', r'^\d+个',
        r'^\d+次', r'^\d+艘', r'^\d+倍', r'^\d+成', r'^\d+股',
        r'^\d+家', r'^\d+只', r'^\d+条', r'^\d+分', r'^\d+秒',
        r'^\d+[\s%]',
        r'^今年', r'^去年', r'^前三季度', r'^上半年', r'^下半年',
        r'^第一季度', r'^第二季度', r'^第三季度', r'^第四季度',
        r'^一季度', r'^二季度', r'^三季度', r'^四季度',
        r'^首季', r'^当季', r'^日内', r'^今日', r'^昨日',
        r'^早盘', r'^午盘', r'^尾盘', r'^隔夜', r'^盘中',
    ]

    changed = True
    while changed and len(cand) >= 2:
        changed = False
        for pat in numeric_prefixes:
            new_cand = re.sub(pat, '', cand).strip()
            if new_cand != cand:
                cand = new_cand
                changed = True
                break

    # 2. 动词、动作、指标、状态、方向性后缀词库（按长度降序，优先剥离复合长词）
    bad_trailings = [
        # 复合动作/趋势
        "大幅上涨", "快速上涨", "持续上涨", "震荡上涨", "小幅上涨", "继续走高",
        "大幅下跌", "快速下跌", "持续下跌", "震荡下跌", "小幅下跌", "继续走低",
        "快速拉升", "震荡调整", "冲高回落", "探底回升", "企稳反弹", "窄幅震荡",
        "大幅波动", "持续走强", "持续走弱", "大幅反弹", "持续回落",
        # 单字/双字动作
        "上演", "飘红", "走高", "走低", "回落", "反弹", "波动", "调整", "大跌", "大涨",
        "暴跌", "暴涨", "领涨", "领跌", "跟涨", "跟跌", "拉升", "下挫", "重挫", "翻红",
        "翻绿", "收官", "加息", "降息", "缩表", "扩表", "降准", "提速", "减速", "升值",
        "贬值", "买入", "卖出", "持股", "减持", "增持", "持仓", "建仓", "平仓", "爆仓",
        "上市", "退市", "破产", "重组", "收购", "合并", "投资", "融资", "贷款", "筹资",
        "取消", "恢复", "调整", "增加", "减少", "发布", "表示", "指出", "宣布", "进行",
        "上涨", "下跌", "飙升", "创", "破", "超", "达", "增", "减", "升至", "跌至",
        "收于", "触及", "刷新", "录得", "扩大", "收窄", "企稳", "走强", "走弱", "收涨",
        "收跌", "高开", "低开", "平开", "涨停", "跌停", "跳空", "回撤", "回调", "探底",
        "冲高", "跳水", "打压", "吸筹", "出货", "换手",
        # 指标/量/状态
        "收益率", "价格", "指数", "汇率", "增速", "同比", "环比", "均价", "现货价",
        "期货", "现货", "收盘价", "走势", "行情", "新高", "新低", "高点", "低点",
        "历史新高", "历史新低", "成交额", "成交量", "持仓量", "市值", "估值",
        # 方向/虚词/量词
        "上", "下", "前", "后", "内", "外", "中", "游", "产", "再", "起", "至", "自",
        "由", "向", "在", "于", "以", "并", "且", "但", "或", "和", "而", "的", "了",
        "着", "过", "已", "将", "被", "把", "让", "使", "及", "等", "个", "只", "家",
        "条", "股", "度", "季", "年", "月", "日", "分", "秒", "左右", "附近", "之上",
        "之下", "以内", "以外",
    ]

    bad_trailings = sorted(set(bad_trailings), key=len, reverse=True)

    changed = True
    while changed and len(cand) >= 2:
        changed = False
        for suffix in bad_trailings:
            if cand.endswith(suffix):
                cand = cand[:-len(suffix)].strip()
                changed = True
                break

    # 3. 最终候选只允许中文、英文字母、空格与连字符；长度 2-8；严禁数字混入
    if re.match(r'^[\u4e00-\u9fa5A-Za-z\s\-]{2,8}$', cand):
        return cand
    return ""


def clean_trailing_incomplete(body_text):
    """
    清理截断文本尾部不完整的连接词、助词或介词短语，确保句子语法完整。
    保守策略：避免误删构成复合词的实义字（如'动向'、'在于'中的'向'/'在'）。
    """
    incompletes = {
        # 多字连接/介词短语（出现在句尾通常意味着句子不完整）
        "进行", "处于", "面临", "针对", "由于", "因为", "所以", "如果", "那么",
        "虽然", "但是", "不仅", "而且", "根据", "按照", "关于", "尽管", "不过",
        # 单字助词（极少作为复合词第二字）
        "的", "了", "着", "过",
    }
    body_text = re.sub(r'[，,；;。！!?？、\s]+$', '', body_text).strip()

    changed = True
    while changed and len(body_text) > 3:
        changed = False
        for word in incompletes:
            if body_text.endswith(word):
                body_text = body_text[:-len(word)].strip()
                body_text = re.sub(r'[，,；;。！!?？、\s]+$', '', body_text).strip()
                changed = True
                break
    return body_text


# ---------------------------------------------------------------------------
# AI 定长摘要层（40-60 字、单中文句号结尾、无省略号）
# ---------------------------------------------------------------------------
def ai_summarize(text):
    """
    轻量级 AI 定长摘要：对全球新闻实施硬性 40-60 字控制与结构规范化。
    格式：【核心实体】+ 精炼事件概述（以单一中文句号收尾）。
    """
    if not isinstance(text, str):
        return "【全球要闻】当前无突发热点，宏观观察哨正对此持续进行高频深度跟踪监控。"

    # 仅当整句被单一层同类型括号完整包裹时才解包；保留【实体】事件描述 结构
    clean_text = text.strip()
    for open_b, close_b in [('【', '】'), ('[', ']'), ('（', '）'), ('(', ')')]:
        if clean_text.startswith(open_b) and clean_text.endswith(close_b):
            inner = clean_text[1:-1].strip()
            # 防止误拆含嵌套同类型括号的文本
            if open_b not in inner and close_b not in inner:
                clean_text = inner
                break
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = clean_text.strip()

    if not clean_text:
        return "【全球要闻】当前无突发热点，宏观观察哨正对此持续进行高频深度跟踪监控。"

    # 1. 提取核心名词实体（只放专有名词/发布主体，长度 2-8 字，不含动词/数字）
    def extract_entity(t):
        # A. 优先匹配原生方括号标签
        m_bracket = re.match(r'^[【\[\(（]([^】\]\)）]+)[】\]\)）]', t)
        if m_bracket:
            candidate = m_bracket.group(1).strip()
            candidate = clean_entity_candidate(candidate)
            if candidate:
                return candidate

        # B. 剥离可能存在的头部括号，从正文主体中识别实体
        text_body = re.sub(r'^[【\[\(（][^】\]\)）]+[】\]\)）]', '', t).strip()

        # B1. 主体 + 常见动作词边界
        verbs = r'(?:发布|表示|指出|宣布|称|公布|报道|警告|印发|公告|举行|开展|建议|强调|警示|印发|下发|取消|恢复|调整|上涨|下跌)'
        match_verb = re.search(r'^([^：，,。—\s【】（）]{2,12}?)(?:' + verbs + r')', text_body)
        if match_verb:
            candidate = clean_entity_candidate(match_verb.group(1))
            if candidate:
                return candidate

        # B2. 常见机构/主体后缀
        org_suffixes = r'(?:厅|部|局|台|委|会|公司|集团|银行|证券|交易所|央行|政府|协会|联社|研究所|中心|企业|媒体|行业|产业|股市|市场|报告|预警|指数|数据|会议|纪要)'
        match_suffix = re.search(r'^([^：，,。—\s【】（）]{2,12}?' + org_suffixes + r')', text_body)
        if match_suffix:
            candidate = clean_entity_candidate(match_suffix.group(1))
            if candidate:
                return candidate

        # B3. 常用宏观名词词库匹配
        entities = [
            "日本央行", "美联储", "欧央行", "英国央行", "国家统计局", "发改委", "商务部",
            "财政部", "交通运输部", "水利厅", "气象局", "气象台", "川崎重工", "日本生命保险",
            "联合国", "世界银行", "欧盟", "中国", "美国", "日本", "英国", "法国", "德国",
            "俄罗斯", "沙特", "欧佩克", "OPEC", "动力煤", "焦煤", "石油", "黄金"
        ]
        for ent in entities:
            if ent in text_body[:20]:
                return ent

        # B4. 兜底匹配最前部的干净名词
        match_noun = re.match(r'^([^：，,。—\s【】（）]{2,8})', text_body)
        if match_noun:
            candidate = clean_entity_candidate(match_noun.group(1))
            if candidate:
                return candidate

        return "全球要闻"

    entity = extract_entity(clean_text)
    prefix = f"【{entity}】"

    # 2. 剥离正文开头的实体前缀与特殊符号，防符号粘连
    text_body = re.sub(r'^[【\[\(（][^】\]\)）]+[】\]\)）]', '', clean_text).strip()
    if text_body.startswith(entity):
        text_body = text_body[len(entity):].lstrip("：，, ")

    # 特殊语法边界纠偏：如 entity="哈萨克斯坦能源部", body="长：" => entity="哈萨克斯坦", body="能源部长："
    regions = ["哈萨克斯坦", "美国", "中国", "日本", "俄罗斯", "英国", "法国", "德国", "印度", "沙特", "乌克兰", "欧盟"]
    for reg in regions:
        if entity.startswith(reg) and entity != reg:
            if text_body.startswith("长") or text_body.startswith("：") or text_body.startswith("表示"):
                dept = entity[len(reg):]
                entity = reg
                prefix = f"【{entity}】"
                text_body = dept + text_body
                break

    # 优化标签衔接过渡
    text_body = re.sub(r'^[：，,。；;！!？?、\s【】\[\]\(\)\（\）\-\—\+]+', '', text_body).strip()
    text_body = re.sub(r'^长(?:：|:)', '部长表示：', text_body)
    text_body = re.sub(r'^([部厅局长官人委台])(?:：|:)', r'\1表示：', text_body)

    # 3. 分句累加组装（前馈防止截断半句）
    clauses = [c.strip() for c in re.split(r'[，,；;。！!？?、]', text_body) if c.strip()]

    accumulated_body = ""
    for c in clauses:
        separator = "，" if accumulated_body else ""
        test_body = accumulated_body + separator + c
        if len(prefix) + len(test_body) + 1 <= 60:
            accumulated_body = test_body
        else:
            break

    # 如果第一句就超过 60 字限制，必须截断并拼接语法完整结尾
    if not accumulated_body and clauses:
        first_clause = clauses[0]
        max_b_len = 60 - len(prefix) - 1
        suffix = "，市场对此高度关注"
        safe_len = max_b_len - len(suffix)
        if safe_len >= 20:
            # 在 safe_len 范围内回退到最近一个完整分句/短语边界
            snippet = first_clause[:safe_len]
            last_punct = max(snippet.rfind('，'), snippet.rfind('、'), snippet.rfind('；'))
            if last_punct > 10:
                snippet = snippet[:last_punct]
            accumulated_body = clean_trailing_incomplete(snippet) + suffix
        else:
            accumulated_body = first_clause[:max_b_len]
            accumulated_body = clean_trailing_incomplete(accumulated_body)

    # 4. 完整分句累加出的 body 保持原貌；仅截断路径已做清洗

    # 5. 二次对齐 [40, 60] 字的物理空间限制
    # 清理 body 中的所有方括号，保证整条快讯有且仅有开头的一套【】
    accumulated_body = accumulated_body.replace("【", "").replace("】", "").replace("[", "").replace("]", "")
    summary = f"{prefix}{accumulated_body}。"
    summary = re.sub(r'。+$', '。', summary)

    if len(summary) < 40:
        # 以完整补充句填充，避免逐字截断造成病句；以逗号自然衔接前文
        full_tail = "，本观察哨对此将持续保持高频监测与深度跟踪分析。"
        candidate = f"{prefix}{accumulated_body}{full_tail}"
        candidate = re.sub(r'。+$', '。', candidate)
        # 若超长则回退到最近完整分句边界
        if len(candidate) > 60:
            truncated = candidate[:59]
            last_punct = max(truncated.rfind('，'), truncated.rfind('、'), truncated.rfind('；'))
            if last_punct > len(prefix) + 5:
                truncated = truncated[:last_punct]
            candidate = truncated + "。"
        summary = candidate

    # 终极越界防护
    if len(summary) > 60:
        summary = summary[:59] + "。"

    return summary
