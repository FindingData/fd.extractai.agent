# app/report/rules/slicing/registry.py
from __future__ import annotations

from typing import Optional

from fd_extractai_report.rules.slicing.schema import SliceRuleSet, merge_rulesets
from fd_extractai_report.rules.slicing.default_rulesets import DEFAULT_RULESETS_BY_TYPE


def validate_ruleset(rs: SliceRuleSet) -> None:
    ok, errors = rs.validate()
    if not ok:
        msg = "\n".join(f"- {e}" for e in errors)
        raise ValueError(f"Slicing ruleset validation failed: {rs.name}\n{msg}")


def merge_ruleset(base: SliceRuleSet, override: SliceRuleSet) -> SliceRuleSet:
    merged = merge_rulesets(base, override, strategy="override_steps")
    validate_ruleset(merged)
    return merged


def get_ruleset(report_type: str, *, override: Optional[SliceRuleSet] = None) -> SliceRuleSet:
    base = DEFAULT_RULESETS_BY_TYPE.get(report_type)
    if not base:
        raise KeyError(f"No SliceRuleSet for report_type={report_type}")

    if override:
        if override.report_type != report_type:
            raise ValueError("override.report_type must match")
        return merge_ruleset(base, override)
    
    validate_ruleset(base)
    return base