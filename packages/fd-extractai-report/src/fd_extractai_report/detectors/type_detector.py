from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .types import BaseDetector, DetectionResult, ReportType


_STRONG_PATTERNS: List[tuple[ReportType, re.Pattern[str], int]] = [
    (
        "house",
        re.compile(
            r"\u623f\u5730\u4ea7\u62b5\u62bc\u4f30\u4ef7\u62a5\u544a|\u81f4\u4f30\u4ef7\u59d4\u6258\u4eba\u51fd"
        ),
        999,
    ),
    (
        "land",
        re.compile(r"\u571f\u5730\u4f30\u4ef7\u62a5\u544a|\u57ce\u9547\u571f\u5730\u4f30\u4ef7\u89c4\u7a0b"),
        999,
    ),
    (
        "asset",
        re.compile(
            r"\u8d44\u4ea7\u8bc4\u4f30\u62a5\u544a(\u4e66|\u6458\u8981|\u6b63\u6587)|\u4e2d\u56fd\u8d44\u4ea7\u8bc4\u4f30\u534f\u4f1a"
        ),
        999,
    ),
    (
        "checklist",
        re.compile(
            r"\u8d44\u6599\u8c03\u53d6\u6e05\u5355|"
            r"\u6240\u9700\u8d44\u6599\u6e05\u5355|"
            r"\u8d37\u6b3e\u8d44\u6599\u6e05\u5355|"
            r"\u62b5\u62bc\u8d44\u6599\u6e05\u5355|"
            r"\u6240\u9700\u63d0\u4ea4\u8d44\u6599|"
            r"\u5173\u4e8e\u5546\u8bf7\u63d0\u4f9b.*\u8d44\u6599.*\u51fd|"
            r"\u8d44\u6599\u8865\u5145\u6e05\u5355|"
            r"\u9700\u8865\u5145\u7684\u8d44\u6599|"
            r"\u5212\u5165\u9879\u76ee\u8c03\u53d6\u8d44\u6599\u6e05\u5355|"
            r"\u9879\u76ee\u9700\u8c03\u53d6\u7684\u8d44\u6599"
        ),
        999,
    ),
]

_HINTS: Dict[ReportType, List[tuple[str, int]]] = {
    "house": [
        ("\u623f\u5730\u4ea7\u62b5\u62bc\u4ef7\u503c", 6),
        ("\u62b5\u62bc\u4ef7\u503c", 3),
        ("\u4f30\u4ef7\u59d4\u6258\u4eba", 3),
        ("\u6ce8\u518c\u623f\u5730\u4ea7\u4f30\u4ef7\u5e08", 5),
        ("\u4f30\u4ef7\u62a5\u544a\u51fa\u5177\u65e5\u671f", 4),
        ("\u4f30\u4ef7\u5bf9\u8c61\u57fa\u672c\u60c5\u51b5\u4e00\u89c8\u8868", 5),
        ("\u4e0d\u52a8\u4ea7\u6743", 3),
    ],
    "land": [
        ("\u571f\u5730\u4f7f\u7528\u6743", 4),
        ("\u5b97\u5730", 4),
        ("\u5bb9\u79ef\u7387", 5),
        ("\u51fa\u8ba9\u5e74\u9650", 4),
        ("\u571f\u5730\u603b\u9762\u79ef", 4),
        ("\u89c4\u5212\u6761\u4ef6\u901a\u77e5\u4e66", 4),
        ("\u56fd\u6709\u571f\u5730\u4f7f\u7528\u8bc1", 5),
        ("\u4e94\u901a", 4),
        ("\u571f\u5730\u767b\u8bb0\u7528\u9014", 4),
    ],
    "asset": [
        ("\u8d44\u4ea7\u8bc4\u4f30", 6),
        ("\u8d44\u4ea7\u8bc4\u4f30\u62a5\u544a\u6458\u8981", 8),
        ("\u8bc4\u4f30\u57fa\u51c6\u65e5", 4),
        ("\u6536\u76ca\u6cd5", 3),
        ("\u65e0\u5f62\u8d44\u4ea7", 6),
        ("\u4e13\u5229\u6743", 6),
        ("\u80a1\u4e1c\u5168\u90e8\u6743\u76ca", 5),
        ("\u673a\u5668\u8bbe\u5907", 5),
    ],
    "checklist": [
        ("\u8d44\u6599\u6e05\u5355", 6),
        ("\u8c03\u53d6\u6e05\u5355", 5),
        ("\u6750\u6599\u6e05\u5355", 5),
        ("\u6240\u9700\u63d0\u4f9b", 4),
        ("\u9700\u63d0\u4f9b\u4ee5\u4e0b\u8d44\u6599", 5),
        ("\u63d0\u4ea4\u6750\u6599", 3),
        ("\u5173\u4e8e\u5546\u8bf7\u63d0\u4f9b", 6),
        ("\u8d44\u6599\u8865\u5145\u6e05\u5355", 7),
        ("\u9700\u8865\u5145\u7684\u8d44\u6599", 7),
        ("\u5212\u5165\u9879\u76ee\u8c03\u53d6\u8d44\u6599\u6e05\u5355", 8),
        ("\u9879\u76ee\u9700\u8c03\u53d6\u7684\u8d44\u6599", 7),
        ("\u6240\u9700\u8d44\u6599\u6e05\u5355", 7),
        ("\u9700\u8c03\u53d6", 4),
        ("\u9700\u8865\u5145", 4),
        ("\u539f\u4ef6", 2),
        ("\u590d\u5370\u4ef6", 2),
    ],
}

_NEG: Dict[ReportType, List[tuple[str, int]]] = {
    "house": [
        ("\u4e2d\u56fd\u8d44\u4ea7\u8bc4\u4f30\u534f\u4f1a", 8),
        ("\u65e0\u5f62\u8d44\u4ea7", 6),
        ("\u4e13\u5229\u6743", 6),
        ("\u571f\u5730\u4f30\u4ef7\u62a5\u544a", 10),
    ],
    "land": [
        ("\u623f\u5730\u4ea7\u62b5\u62bc\u4f30\u4ef7\u62a5\u544a", 10),
        ("\u81f4\u4f30\u4ef7\u59d4\u6258\u4eba\u51fd", 6),
        ("\u8d44\u4ea7\u8bc4\u4f30\u62a5\u544a", 10),
    ],
    "asset": [
        ("\u623f\u5730\u4ea7\u62b5\u62bc\u4f30\u4ef7\u62a5\u544a", 10),
        ("\u81f4\u4f30\u4ef7\u59d4\u6258\u4eba\u51fd", 8),
        ("\u571f\u5730\u4f30\u4ef7\u62a5\u544a", 10),
        ("\u56fd\u6709\u571f\u5730\u4f7f\u7528\u8bc1", 4),
    ],
    "checklist": [
        ("\u623f\u5730\u4ea7\u62b5\u62bc\u4f30\u4ef7\u62a5\u544a", 10),
        ("\u571f\u5730\u4f30\u4ef7\u62a5\u544a", 10),
        ("\u8d44\u4ea7\u8bc4\u4f30\u62a5\u544a", 10),
        ("\u81f4\u4f30\u4ef7\u59d4\u6258\u4eba\u51fd", 8),
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

        for rtype, pat, _ in _STRONG_PATTERNS:
            m = pat.search(head)
            if m:
                scores = {rt: 0 for rt in _HINTS}
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

        def weighted_score(rt: ReportType) -> Tuple[int, list, list]:
            hits = []
            score = 0
            for token, weight in _HINTS[rt]:
                if token in head:
                    score += weight
                    hits.append((token, weight))

            neg_hits = []
            for token, weight in _NEG[rt]:
                if token in head:
                    score -= weight
                    neg_hits.append((token, -weight))
            return score, hits, neg_hits

        scores: Dict[str, int] = {}
        debug_hits: Dict[str, list] = {}
        debug_negs: Dict[str, list] = {}

        for rt in _HINTS:
            score, hits, negs = weighted_score(rt)  # type: ignore[arg-type]
            scores[rt] = score
            debug_hits[rt] = hits
            debug_negs[rt] = negs

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        top, top_score = ranked[0]
        second, second_score = ranked[1]

        min_score = int(kwargs.get("min_score") or self.config.min_score)
        min_gap = int(kwargs.get("min_gap") or self.config.min_gap)

        if top_score < min_score or (top_score - second_score) < min_gap:
            default_type = self.config.default_type
            info = {
                "mode": "low_confidence",
                "reason": "low_confidence_default",
                "scores": scores,
                "top": (top, top_score),
                "second": (second, second_score),
                "hits": debug_hits,
                "negs": debug_negs,
                "thresholds": {"min_score": min_score, "min_gap": min_gap},
                "default": default_type,
            }
            return DetectionResult(report_type=default_type, info=info, confidence=0.3)

        info = {
            "mode": "weighted",
            "reason": "weighted_top",
            "scores": scores,
            "top": (top, top_score),
            "second": (second, second_score),
            "hits": debug_hits,
            "negs": debug_negs,
            "thresholds": {"min_score": min_score, "min_gap": min_gap},
        }
        gap = max(0, top_score - second_score)
        confidence = min(0.95, 0.5 + gap / 20.0)
        return DetectionResult(report_type=top, info=info, confidence=confidence)  # type: ignore[arg-type]
