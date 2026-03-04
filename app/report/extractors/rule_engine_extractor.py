from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional

from langextract.core import data as lxdata
from app.report.context import ReportContext
from app.report.extractors.base import Extractor
from app.report.rules.extracting.registry import get_ruleset
from app.report.rules.extracting.schema import ExtractRuleSet, ExtractorSpec


class RuleEngineExtractorRunner:
    def __init__(self, *, debug: bool = True, model_id: Optional[str] = None, model_url: Optional[str] = None):
        self.debug = debug
        self.model_id = model_id
        self.model_url = model_url

    def run(self, context: ReportContext, *, override: Optional[ExtractRuleSet] = None) -> Dict[str, List[dict]]:
        rt = (context.metadata or {}).get("report_type") or "house"
        rs = get_ruleset(rt, override=override)

        results: Dict[str, List[dict]] = {}

        for i, spec in enumerate(rs.extractors):
            if not spec.enabled:
                if self.debug:
                    print(f"[Extract][SKIP] #{i} slug={spec.slug} (disabled)")
                continue

            merged = self._inherit_ruleset_defaults(spec, rs)
            if self.debug:
                print(f"[Extract][DBG] merged.slug={merged.slug!r}")                
            ex_examples = ()
            spec_examples = getattr(merged, "examples", None)
            if isinstance(spec_examples, dict):
                ex_examples = spec_examples.get(rt) or spec_examples.get("general") or ()
            # ✅ 类型强校验：宁可早炸，也别传错类型导致后面变成 str
            bad = [e for e in (ex_examples or ()) if not isinstance(e, lxdata.ExampleData)]
            if bad:
                raise TypeError(
                    f"Invalid examples for slug={merged.slug}, rt={rt}. "
                    f"Expect ExampleData, got: {[type(x).__name__ for x in bad]}"
                )

            ex = Extractor(spec=merged, model_id=self.model_id, model_url=self.model_url,examples=ex_examples)

            # 可观测性：输入统计
            if self.debug:
                text = ex.get_input_text(context)
                print(
                    f"[Extract][START] #{i} slug={merged.slug} keys={merged.input_slice_keys} "
                    f"chars={len(text)} policy={merged.missing_slice_policy}"
                )

            rows = ex(context) or []

            if self.debug:
                print(f"[Extract][DONE]  slug={merged.slug} rows={len(rows)}")

            out_key = merged.output_key or merged.slug
            results[out_key] = rows

        return results

    def _inherit_ruleset_defaults(self, spec: ExtractorSpec, rs: ExtractRuleSet) -> ExtractorSpec:
        inject = list(rs.inject_context_fields or [])
        for f in (spec.inject_context_fields or []):
            if f not in inject:
                inject.append(f)

        max_chars = spec.max_input_chars
        if rs.max_input_chars is not None:
            max_chars = rs.max_input_chars

        return replace(spec, inject_context_fields=inject, max_input_chars=max_chars)