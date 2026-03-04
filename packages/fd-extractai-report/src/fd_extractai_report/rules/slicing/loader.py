from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fd_extractai_report.rules.slicing.schema import SliceRuleSet, SliceStep


def ruleset_from_dict(d: Dict[str, Any]) -> SliceRuleSet:
    steps = []
    for sd in d.get("steps", []) or []:
        steps.append(
            SliceStep(
                key=sd["key"],
                mode=sd["mode"],
                targets=list(sd.get("targets", []) or []),
                within=sd.get("within"),
                params=dict(sd.get("params", {}) or {}),
                missing=sd.get("missing", "empty"),
            )
        )

    rs = SliceRuleSet(
        name=d.get("name", "") or "unnamed",
        defaults=dict(d.get("defaults", {}) or {}),
        steps=steps,
    )
    return rs


def ruleset_from_json_text(text: str) -> SliceRuleSet:
    return ruleset_from_dict(json.loads(text))


def ruleset_from_json_file(path: str) -> SliceRuleSet:
    with open(path, "r", encoding="utf-8") as f:
        return ruleset_from_json_text(f.read())


def ruleset_from_yaml_text(text: str) -> SliceRuleSet:
    """
    可选：需要 PyYAML（yaml）依赖。没有安装就抛出清晰错误。
    """
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise RuntimeError("PyYAML is required for YAML ruleset loading. Install pyyaml.") from e

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML ruleset root must be a mapping/dict.")
    return ruleset_from_dict(data)


def ruleset_from_yaml_file(path: str) -> SliceRuleSet:
    with open(path, "r", encoding="utf-8") as f:
        return ruleset_from_yaml_text(f.read())