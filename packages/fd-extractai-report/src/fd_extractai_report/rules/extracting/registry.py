# app/report/rules/extracting/registry.py
from __future__ import annotations

from dataclasses import replace
from typing import Dict, Optional

from fd_extractai_report.rules.extracting.schema import ExtractRuleSet, ExtractorSpec, validate_ruleset
from fd_extractai_report.rules.extracting.default_rulesets import DEFAULT_RULESETS

def merge_ruleset(base: ExtractRuleSet, override: ExtractRuleSet) -> ExtractRuleSet:
    # 1) ruleset-level 覆盖
    rs = replace(
        base,
        inject_context_fields=override.inject_context_fields or base.inject_context_fields,
        max_input_chars=override.max_input_chars if override.max_input_chars is not None else base.max_input_chars,
    )

    # 2) extractor-level merge by slug
    by_slug: Dict[str, ExtractorSpec] = {e.slug: e for e in rs.extractors}
    order = [e.slug for e in rs.extractors]

    for oe in override.extractors:
        if oe.slug in by_slug:
            be = by_slug[oe.slug]
            # 用 override 中“显式提供”的字段覆盖（这里用简单规则：全覆盖）
            by_slug[oe.slug] = replace(
                be,
                prompt_filename=oe.prompt_filename or be.prompt_filename,
                input_slice_keys=oe.input_slice_keys or be.input_slice_keys,
                missing_slice_policy=oe.missing_slice_policy or be.missing_slice_policy,
                defaults=oe.defaults or be.defaults,
                inject_context_fields=oe.inject_context_fields or be.inject_context_fields,
                add_titles=oe.add_titles,
                max_input_chars=oe.max_input_chars or be.max_input_chars,
                output_key=oe.output_key or be.output_key,
                enabled=oe.enabled,
            )
        else:
            by_slug[oe.slug] = oe
            order.append(oe.slug)

    rs = replace(rs, extractors=[by_slug[s] for s in order])
    validate_ruleset(rs)
    return rs

def get_ruleset(report_type: str, *, override: Optional[ExtractRuleSet] = None) -> ExtractRuleSet:
    base = DEFAULT_RULESETS.get(report_type)
    if not base:
        raise KeyError(f"No ExtractRuleSet for report_type={report_type}")

    if override:
        if override.report_type != report_type:
            raise ValueError("override.report_type must match")
        return merge_ruleset(base, override)
    return base