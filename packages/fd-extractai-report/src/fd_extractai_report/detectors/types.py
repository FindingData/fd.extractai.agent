from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


ReportType = Literal["house", "land", "asset"]


@dataclass(frozen=True)
class DetectionResult:
    report_type: ReportType
    info: Dict[str, Any]
    confidence: Optional[float] = None  # 先留口，后面你想算置信度可加


class BaseDetector:
    """所有 detector 的统一接口（以后你还可以加 region/company/whatever detector）"""

    def detect(self, text: str, **kwargs) -> DetectionResult:  # pragma: no cover
        raise NotImplementedError