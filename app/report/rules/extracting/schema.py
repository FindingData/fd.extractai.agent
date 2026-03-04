# app/report/rules/extracting/schema.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union, Literal

from langextract.core import data

ExampleSpec = Union[
    Sequence[data.ExampleData],
    Mapping[str, Sequence[data.ExampleData]],  # {"house":[...], "fallback":[...]}
]

MissingPolicy = Literal["empty", "full", "raise"]

@dataclass
class ExtractorSpec:
    slug: str
    prompt_filename: str

    input_slice_keys: List[str] = field(default_factory=lambda: ["__full__"])
    missing_slice_policy: MissingPolicy = "empty"

    examples: ExampleSpec = field(default_factory=tuple)

    defaults: Dict[str, Any] = field(default_factory=dict)
    inject_context_fields: List[str] = field(default_factory=list)

    add_titles: bool = True
    max_input_chars: int = 12000

    # ✅ 把抽取结果放到 context 的哪个 bucket（可选）
    output_key: Optional[str] = None

    # ✅ 允许临时禁用某个抽取器（调试/灰度）
    enabled: bool = True

@dataclass
class ExtractRuleSet:
    """
    一份报告类型对应的一组抽取器定义（pipeline）。
    """
    name: str
    report_type: str

    # 按顺序执行（很多抽取是相互独立的，但顺序可控更好调试）
    extractors: List[ExtractorSpec] = field(default_factory=list)

    # 可选：全局默认注入字段（每个 extractor 都会继承）
    inject_context_fields: List[str] = field(default_factory=list)

    # 可选：全局默认 max_input_chars
    max_input_chars: Optional[int] = None

    examples: Sequence[data.ExampleData] = ()    

def validate_ruleset(rs: ExtractRuleSet) -> None:
    seen = set()
    for ex in rs.extractors:
        if not ex.slug:
            raise ValueError("ExtractorSpec.slug is required")
        if ex.slug in seen:
            raise ValueError(f"Duplicate extractor slug: {ex.slug}")
        seen.add(ex.slug)

        if ex.missing_slice_policy not in ("empty", "full", "raise"):
            raise ValueError(f"Invalid missing_slice_policy: {ex.missing_slice_policy}")

        if not ex.prompt_filename:
            raise ValueError(f"Extractor '{ex.slug}' prompt_filename is required")