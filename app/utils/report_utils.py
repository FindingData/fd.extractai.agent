import re
from typing import Literal, Tuple, Dict, List

ReportType = Literal["house", "land", "asset"]

# -------- 1) 强特征：命中就直接判定（更稳） --------
_STRONG_PATTERNS: List[tuple[ReportType, re.Pattern, int]] = [
    ("house", re.compile(r"房地产抵押估价报告|致估价委托人函"), 999),
    ("land",  re.compile(r"土地估价报告|城镇土地估价规程"), 999),
    ("asset", re.compile(r"资产评估报告(书|摘要|正文)|中国资产评估协会"), 999),
]

# -------- 2) 加权 hints：建议只放“区分度高”的词 --------
_HINTS: Dict[ReportType, List[tuple[str, int]]] = {
    "house": [
        ("房地产抵押价值", 6),
        ("抵押价值", 3),
        ("估价委托人", 3),
        ("注册房地产估价师", 5),
        ("估价报告出具日期", 4),
        ("估价对象基本情况一览表", 5),
        ("不动产权", 3),
    ],
    "land": [
        ("土地使用权", 4),
        ("宗地", 4),
        ("容积率", 5),
        ("出让年限", 4),
        ("土地总面积", 4),
        ("规划条件通知书", 4),
        ("国有土地使用证", 5),
        ("五通", 4),
        ("土地登记用途", 4),
    ],
    "asset": [
        ("资产评估", 6),
        ("资产评估报告摘要", 8),
        ("评估基准日", 4),
        ("收益法", 3),
        ("无形资产", 6),
        ("专利权", 6),
        ("股东全部权益", 5),
        ("机器设备", 5),
    ],
}

# -------- 3) 负向特征：用于“打断误判” --------
_NEG: Dict[ReportType, List[tuple[str, int]]] = {
    # house 文本里若出现这些，更像 asset/land，则扣分
    "house": [
        ("中国资产评估协会", 8),
        ("无形资产", 6),
        ("专利权", 6),
        ("土地估价报告", 10),
    ],
    "land": [
        ("房地产抵押估价报告", 10),
        ("致估价委托人函", 6),
        ("资产评估报告", 10),
    ],
    "asset": [
        ("房地产抵押估价报告", 10),
        ("致估价委托人函", 8),
        ("土地估价报告", 10),
        ("国有土地使用证", 4),  # asset 里也可能引用，但一般不在开头高频
    ],
}

def _normalize_head(text: str) -> str:
    head = (text or "")
    # 保留少量结构：把连续空白压缩为 1 个空格，不要全部去掉
    head = re.sub(r"\s+", " ", head).strip()
    # 去掉一些干扰符号（可按你实际 md 产出再加）
    head = head.replace("\u3000", " ")
    return head

def detect_report_type_from_md_head(md_text: str, head_chars: int = 2000) -> Tuple[ReportType, dict]:
    """
    只看 markdown 开头片段做类型识别（增强规则版）。
    返回：(report_type, debug_info)
    """
    head = _normalize_head((md_text or "")[:head_chars])

    # 1) 强特征：命中直接返回（最高优先级）
    for rtype, pat, _ in _STRONG_PATTERNS:
          m = pat.search(head)
          if m:
            strong_scores = {"house": 0, "land": 0, "asset": 0}
            strong_scores[rtype] = 999
            return rtype, {
                "reason": "strong_match",
                "scores": strong_scores,
                "strong_hit": pat.pattern,
                "strong_text": m.group(0),
                "strong_span": (m.start(), m.end()),
            }

    # 2) 加权打分（记录命中项）
    def weighted_score(rtype: ReportType):
        hits = []
        score = 0
        for token, w in _HINTS[rtype]:
            if token in head:
                score += w
                hits.append((token, w))
        # 负向扣分
        neg_hits = []
        for token, w in _NEG[rtype]:
            if token in head:
                score -= w
                neg_hits.append((token, -w))
        return score, hits, neg_hits

    scores = {}
    debug_hits = {}
    debug_negs = {}
    for t in ("house", "land", "asset"):
        s, hits, negs = weighted_score(t)  # type: ignore
        scores[t] = s
        debug_hits[t] = hits
        debug_negs[t] = negs

    # 3) 决策：最高分 + 置信度阈值 + 差距阈值
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top, topv = ranked[0]
    second, secondv = ranked[1]

    # 可调参数：你可以根据线上数据回放微调
    MIN_SCORE = 6          # 低于这个分数就算“没把握”
    MIN_GAP = 3            # 第一名比第二名至少多 3 分才算稳定

    if topv < MIN_SCORE or (topv - secondv) < MIN_GAP:
        # 低置信度：你也可以改成返回 "house" 但标记 low_confidence
        return "house", {
            "reason": "low_confidence_default_house",
            "scores": scores,
            "top": (top, topv),
            "second": (second, secondv),
            "hits": debug_hits,
            "negs": debug_negs,
        }

    return top, {
        "reason": "weighted_top",
        "scores": scores,
        "top": (top, topv),
        "second": (second, secondv),
        "hits": debug_hits,
        "negs": debug_negs,
    }