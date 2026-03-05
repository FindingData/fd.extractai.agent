from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .types import BaseDetector, DetectionResult, ReportType


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
        ("国有土地使用证", 4),
    ],
}


def _normalize_head(text: str) -> str:
    head = (text or "")
    head = re.sub(r"\s+", " ", head).strip()
    head = head.replace("\u3000", " ")
    return head


@dataclass(frozen=True)
class ReportTypeDetectorConfig:
    head_chars: int = 2000
    min_score: int = 6
    min_gap: int = 3
    default_type: ReportType = "house"


class ReportTypeDetector(BaseDetector):
    def __init__(self, config: ReportTypeDetectorConfig | None = None) -> None:
        self.config = config or ReportTypeDetectorConfig()

    def detect(self, text: str, **kwargs) -> DetectionResult:
        head_chars = int(kwargs.get("head_chars") or self.config.head_chars)
        head = _normalize_head((text or "")[:head_chars])

        # 1) strong match
        for rtype, pat, _ in _STRONG_PATTERNS:
            m = pat.search(head)
            if m:
                scores = {"house": 0, "land": 0, "asset": 0}
                scores[rtype] = 999
                info = {
                    "mode": "strong",
                    "reason": "strong_match",
                    "scores": scores,
                    "strong_hit": pat.pattern,
                    "strong_text": m.group(0),
                    "strong_span": (m.start(), m.end()),
                }
                return DetectionResult(report_type=rtype, info=info, confidence=1.0)

        # 2) weighted
        def weighted_score(rt: ReportType) -> Tuple[int, list, list]:
            hits = []
            score = 0
            for token, w in _HINTS[rt]:
                if token in head:
                    score += w
                    hits.append((token, w))

            neg_hits = []
            for token, w in _NEG[rt]:
                if token in head:
                    score -= w
                    neg_hits.append((token, -w))
            return score, hits, neg_hits

        scores: Dict[str, int] = {}
        debug_hits: Dict[str, list] = {}
        debug_negs: Dict[str, list] = {}

        for rt in ("house", "land", "asset"):
            s, hits, negs = weighted_score(rt)  # type: ignore[arg-type]
            scores[rt] = s
            debug_hits[rt] = hits
            debug_negs[rt] = negs

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top, topv = ranked[0]
        second, secondv = ranked[1]

        min_score = int(kwargs.get("min_score") or self.config.min_score)
        min_gap = int(kwargs.get("min_gap") or self.config.min_gap)

        if topv < min_score or (topv - secondv) < min_gap:
            default_type = self.config.default_type
            info = {
                "mode": "low_confidence",
                "reason": "low_confidence_default",
                "scores": scores,
                "top": (top, topv),
                "second": (second, secondv),
                "hits": debug_hits,
                "negs": debug_negs,
                "thresholds": {"min_score": min_score, "min_gap": min_gap},
                "default": default_type,
            }
            # 置信度随便给个“低”的占位（以后你要做更严谨再说）
            return DetectionResult(report_type=default_type, info=info, confidence=0.3)

        info = {
            "mode": "weighted",
            "reason": "weighted_top",
            "scores": scores,
            "top": (top, topv),
            "second": (second, secondv),
            "hits": debug_hits,
            "negs": debug_negs,
            "thresholds": {"min_score": min_score, "min_gap": min_gap},
        }
        # 简单置信度：gap 越大越高（只是启发式）
        gap = max(0, topv - secondv)
        confidence = min(0.95, 0.5 + gap / 20.0)
        return DetectionResult(report_type=top, info=info, confidence=confidence)  # type: ignore[arg-type]