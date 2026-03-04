from dataclasses import dataclass
from typing import Sequence, Dict
from app.utils.report_utils import ReportType

@dataclass(frozen=True)
class ReportProfile:
    report_type: str
    slicers: Sequence
    extractors: Sequence
    # 可选：不同类型的“抽取规则包”（prompt路径、few-shot、schema版本等）
    rules: Dict[str, object] | None = None


class ReportProfileRegistry:
    def __init__(self, profiles: Dict[str, ReportProfile], default_profile: ReportProfile):
        self.profiles = profiles
        self.default = default_profile

    def get(self, report_type: str) -> ReportProfile:
        return self.profiles.get(report_type) or self.default