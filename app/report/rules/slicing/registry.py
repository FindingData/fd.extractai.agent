from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Literal

from app.report.rules.slicing.schema import SliceRuleSet, MergeStrategy, merge_rulesets
from app.report.rules.slicing.default_rulesets import DEFAULT_RULESETS_BY_TYPE, RULESET_HOUSE


ReportType = Literal["house", "land", "asset"]


@dataclass
class SlicingRuleRegistry:
    """
    规则注册表：
    - 内置 defaults（house/land/asset）
    - 支持外部 overrides：
        - replace：整套替换
        - override_steps：按 step.key 覆盖/新增（推荐）
        - append_steps：追加
    """
    defaults_by_type: Dict[str, SliceRuleSet] = field(default_factory=lambda: dict(DEFAULT_RULESETS_BY_TYPE))
    default_type: str = "house"

    # 外部覆盖：report_type -> ruleset
    overrides_by_type: Dict[str, SliceRuleSet] = field(default_factory=dict)
    override_strategy: MergeStrategy = "override_steps"

    def get(self, report_type: Optional[str]) -> SliceRuleSet:
        rt = report_type or self.default_type
        base = self.defaults_by_type.get(rt) or self.defaults_by_type.get(self.default_type) or RULESET_HOUSE

        ov = self.overrides_by_type.get(rt)
        if not ov:
            return base

        merged = merge_rulesets(base, ov, strategy=self.override_strategy)
        return merged

    def set_override(self, report_type: str, ruleset: SliceRuleSet) -> None:
        self.overrides_by_type[report_type] = ruleset

    def validate(self, report_type: Optional[str]) -> None:
        rs = self.get(report_type)
        ok, errors = rs.validate()
        if not ok:
            msg = "\n".join(f"- {e}" for e in errors)
            raise ValueError(f"Slicing ruleset validation failed: {rs.name}\n{msg}")