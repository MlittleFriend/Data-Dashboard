# -*- coding: utf-8 -*-
"""
sentiment_analyzer.py | 外部第三方情感极性分析技能 (V1.1.3)
"""


def analyze_sentiment(text: str) -> dict:
    """
    对输入文本执行轻量级情感分析，分析其中的正面/负面情绪比例。
    """
    if not text:
        return {"sentiment": "neutral", "positive_score": 0.5, "negative_score": 0.5}
        
    pos_words = ["上涨", "增加", "回升", "红", "高位", "创新高", "扩大", "提升", "热销", "增开"]
    neg_words = ["下跌", "减少", "回落", "绿", "低位", "创新低", "缩小", "下降", "跳水", "亏损"]
    
    pos_count = sum(1 for w in pos_words if w in text)
    neg_count = sum(1 for w in neg_words if w in text)
    
    if pos_count > neg_count:
        return {"sentiment": "positive", "positive_score": 0.8, "negative_score": 0.2}
    elif neg_count > pos_count:
        return {"sentiment": "negative", "positive_score": 0.2, "negative_score": 0.8}
    else:
        return {"sentiment": "neutral", "positive_score": 0.5, "negative_score": 0.5}
