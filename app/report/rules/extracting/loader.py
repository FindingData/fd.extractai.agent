# app/report/rules/extracting/loader.py
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.report.rules.extracting.schema import ExtractRuleSet, ExtractorSpec, validate_ruleset

def ruleset_from_dict(d: Dict[str, Any]) -> ExtractRuleSet:
    ex_specs = []
    for item in d.get("extractors", []):
        ex_specs.append(ExtractorSpec(
            slug=item["slug"],
            prompt_filename=item["prompt_filename"],
            input_slice_keys=item.get("input_slice_keys", ["__full__"]),
            missing_slice_policy=item.get("missing_slice_policy", "empty"),
            defaults=item.get("defaults", {}) or {},
            inject_context_fields=item.get("inject_context_fields", []) or [],
            add_titles=item.get("add_titles", True),
            max_input_chars=item.get("max_input_chars", 12000),
            output_key=item.get("output_key"),
            enabled=item.get("enabled", True),
            # examples 这里先不从 yaml 解析（建议走 registry/ref）
        ))

    rs = ExtractRuleSet(
        name=d["name"],
        report_type=d["report_type"],
        extractors=ex_specs,
        inject_context_fields=d.get("inject_context_fields", []) or [],
        max_input_chars=d.get("max_input_chars"),
    )
    validate_ruleset(rs)
    return rs

def ruleset_from_yaml(path: str | Path) -> ExtractRuleSet:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return ruleset_from_dict(data)