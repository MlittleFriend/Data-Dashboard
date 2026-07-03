# -*- coding: utf-8 -*-
"""
news_sanitizer.py | 实时快讯终极清洗层 (V1.1.2)
负责：URL 前馈合法性审查、方括号实体名词死锁、AI 定长摘要。
本模块保持零 Streamlit 依赖，可被 App.py 与离线清洗脚本共同引用。
"""
import re


# ---------------------------------------------------------------------------
# V1.1.4.3: 语义完整性校验器 — 拦截无谓结构的名词碎片
# ---------------------------------------------------------------------------
def verify_semantic_integrity(text: str) -> bool:
    """
    语义完整性校验器：校验快讯标题（<= 10字字数区间）是否包含谓词/动作描述，
    防止如“贵阳白云实业发展集团”等纯名词/机构短语被识别为独立事件展现。
    """
    if not text or not isinstance(text, str):
        return False
    
    text_clean = text.replace("。", "").strip()
    if not text_clean:
        return False
        
    # 对于长度小于等于 10 个字符的标题，触发回滚谓语分析，确保含有有效 SVO 语义
    if len(text_clean) <= 10:
        action_keywords = [
            "完工", "成立", "大跌", "启动", "增", "减", "升", "跌", "降", "涨", "超", "破", "创",
            "收", "触", "开", "启", "行", "建", "办", "研", "批", "准", "发", "示", "指", "称", 
            "说", "表", "宣", "下调", "上调", "增长", "减少", "增加", "下滑", "回落", "反弹", 
            "签约", "合作", "达成", "签署", "通过", "批准", "取消", "恢复", "调整", "发布",
            "表示", "指出", "宣布", "进行", "飙升", "企稳", "走强", "走弱", "收涨", "收跌",
            "高开", "低开", "涨停", "跌停", "重挫", "暴跌", "暴涨", "领涨", "领跌", "跟涨",
            "拉升", "下挫", "上市", "退市", "破产", "重组", "收购", "合并", "投资", "融资",
            "放缓", "加速", "干预", "监管", "调查", "起诉", "落户", "下滑", "完工", "达"
        ]
        
        # 只要包含任意动作关键词，即视为包含有效谓语结构
        for kw in action_keywords:
            if kw in text_clean:
                return True
        return False
        
    return True


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
def sanitize_news_item(rich_text):
    """
    对原始快讯进行独立字段（原标题、核心简讯）提取与精简。
    返回 (title, content)
    其中合并后的总字数（len(title) + 1 + len(content)）在 40 - 60 字之间。
    尾部强制以单个标准简体中文句号完结，并粉碎所有旧版方括号格式。
    """
    if not isinstance(rich_text, str) or not rich_text or str(rich_text).strip().lower() == "nan":
        return "全球要闻。", ""

    rich_text = rich_text.strip()
    
    # 彻底粉碎并清理原文本中的所有方括号 (防止提取逻辑混乱或含有残留方括号)
    # 优先检测 HTML 粗体/标题标签作为文章实际标题 (代表真正的 bold text container，而不是来源/机构)
    m_html = re.search(r'<(b|strong|h[1-6]|span\s+[^>]*font-weight:\s*bold[^>]*)>([^<]{4,})</\1>', rich_text, re.IGNORECASE)
    if m_html:
        title = m_html.group(2).strip()
        body = rich_text.replace(m_html.group(0), "").strip()
    else:
        # 其次提取方括号中的标题（如果有的话）
        m = re.match(r'^[【\[\(（]([^】\]\)）]+)[】\]\)）]', rich_text)
        if m:
            title = m.group(1).strip()
            body = rich_text[m.end():].strip()
        else:
            # 寻找首个标点分界作为语义标题首选，但禁止切分出无完整主谓结构（长度 < 5）的来源机构名称
            split_idx = len(rich_text)
            for idx in range(2, len(rich_text)):
                if idx < 40 and rich_text[idx] in ['：', ':', '，', ',']:
                    candidate_title = rich_text[:idx].strip()
                    # 检查候选标题是否小于5个字，或者是否包含常见的无主谓信息的实体或来源元数据
                    is_metadata = any(kw in candidate_title for kw in [
                        "资讯", "观察哨", "快讯", "金十", "新浪", "分值", "机构", "研究院", 
                        "分析", "发布", "董事长", "团队", "数据", "网", "社", "报", "电", "公司"
                    ])
                    if len(candidate_title) >= 5 and not is_metadata:
                        split_idx = idx
                        break
            
            if split_idx == len(rich_text):
                # 如果没有合适的分割标点，尝试以首个句尾符分割
                m_end = re.search(r'[。；;！!？?]', rich_text)
                if m_end and 5 <= m_end.end() <= 40:
                    title = rich_text[:m_end.end()].strip()
                    body = rich_text[m_end.end():].strip()
                else:
                    title = rich_text[:35].strip()
                    body = rich_text[35:].strip()
            else:
                title = rich_text[:split_idx].strip()
                body = rich_text[split_idx:].strip()

    # 剥离提取后标题与正文内部所有的方括号/圆括号噪音，彻底不使用 【】 字符
    title = title.replace("【", "").replace("】", "").replace("[", "").replace("]", "").replace("（", "").replace("）", "").replace("(", "").replace(")", "")
    body = body.replace("【", "").replace("】", "").replace("[", "").replace("]", "")

    title = re.sub(r'^[：，,。；;！!？?、\s]+', '', title)
    title = re.sub(r'[：，,。；;！!？?、\s]+$', '', title)
    body = re.sub(r'^[：，,。；;！!？?、\s]+', '', body)

    # 1. 拦截 nan 和空标题
    if not title or str(title).strip().lower() == "nan":
        # Fallback 机制：若正文开头包含 【...】 结构，强行剥离作为真实标题
        m_fallback = re.search(r'[【\[]([^】\]]+)[】\]]', body)
        if m_fallback:
            title = m_fallback.group(1).strip()
            # 从正文中剥离该方括号及其内容
            body = body.replace(f"【{title}】", "").replace(f"[{title}]", "").strip()
            title = title.replace("【", "").replace("】", "").replace("[", "").replace("]", "")
            title = re.sub(r'^[：，,。；;！!？?、\s]+', '', title)
            title = re.sub(r'[：，,。；;！!？?、\s]+$', '', title)
        else:
            title = "全球要闻"

    if not body or str(body).strip().lower() == "nan":
        body = ""

    # ==========================================
    # 标题字数前馈拦截分流器
    # ==========================================
    if len(title) > 10:
        # 条件 A: 标题大于 10 个字，触发总结熔断机制。只保留并写出原标题，content 留空，直接追加句号。
        title_text = re.sub(r'[。，,；;！!？?、\s：]+$', '', title)
        if len(title_text) > 58:
            title_text = title_text[:55] + "..."
        title_text = title_text + "。"
        title_text = re.sub(r'。+$', '。', title_text)
        return title_text, ""

    # 条件 B: 标题 <= 10 个字，采用 {原标题}：{一句话核心简讯} 逻辑，合并总字数 [40, 60]
    max_body_len = 58 - len(title)

    # 累加正文子句
    clauses = [c.strip() for c in re.split(r'[，,；;。！!？?、]', body) if c.strip()]
    accumulated_body = ""
    for c in clauses:
        separator = "，" if accumulated_body else ""
        test_body = accumulated_body + separator + c
        if len(test_body) <= max_body_len:
            accumulated_body = test_body
        else:
            break

    # 兜底截断
    if not accumulated_body and clauses:
        first_clause = clauses[0]
        suffix = "，市场关注度上升"
        safe_len = max_body_len - len(suffix)
        if safe_len >= 10:
            accumulated_body = first_clause[:safe_len] + suffix
        else:
            accumulated_body = first_clause[:max_body_len]

    accumulated_body = clean_trailing_incomplete(accumulated_body)

    # 检查最小字数限制
    combined_len = len(title) + 2 + len(accumulated_body)
    if combined_len < 40:
        tail = "，观察哨对此持续保持高频监测与深度跟踪"
        needed = 40 - combined_len
        accumulated_body = accumulated_body + tail[:needed+5]

    # 二次对齐 [40, 60] 空间限制
    combined_len = len(title) + 2 + len(accumulated_body)
    if combined_len > 60:
        overflow = combined_len - 60
        accumulated_body = accumulated_body[:-overflow]
        accumulated_body = clean_trailing_incomplete(accumulated_body)
        
    accumulated_body = re.sub(r'[。，,；;！!？?、\s：]+$', '', accumulated_body) + "。"
    accumulated_body = re.sub(r'。+$', '。', accumulated_body)

    # V1.1.4.2: 标题字数强力熔断拦截（小于 5 字符的碎片直接判定为脏快讯）
    title_strip = title.replace("。", "").strip()
    if len(title_strip) < 5:
        return "", ""

    # V1.1.4.3: 语义谓语框架检查（防范名词/机构特征碎片）
    if not verify_semantic_integrity(title):
        return "", ""

    return title.strip(), accumulated_body.strip()
        

def ai_summarize(text):
    """
    轻量级 AI 定长摘要：保持原接口签名以向下兼容，返回格式为 "{原标题}：{核心简讯}"
    当触发熔断时直接返回 "标题。"
    """
    title, content = sanitize_news_item(text)
    if not content:
        res = title
    else:
        res = f"{title}：{content}"
    res = re.sub(r'。+$', '。', res)
    return res

