from __future__ import annotations

from typing import Dict, List, Sequence

from langextract.core import data

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.examples.report_examples import EXAMPLES_BY_TYPE  # ✅ 你前面那份
from app.report.extractors.aware import ReportTypeAwareExtractor
from app.report.context import ReportContext


class AssumptionsExtractor(ReportTypeAwareExtractor):
    slug = "assumptions"
    target_slice_key = "__full__"
    prompt_filename = "assumptions.txt"

    # ✅ 兜底：识别不到 report_type 时用通用 examples
    fallback_examples = GENERAL_EXAMPLES["assumptions"]

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        if report_type in ("house", "land", "asset"):
            return EXAMPLES_BY_TYPE[report_type]["assumptions"]
        return ()

    def post_process(self, annotated_doc, *, context: ReportContext) -> List[Dict]:
        rows = super().post_process(annotated_doc, context=context)
        for row in rows:
            row["category"] = row.get("category") or "重要假设"
            # ✅ 顺便带上 report_type，后续你合并结构很方便
            row.setdefault("report_type", (context.metadata or {}).get("report_type"))
        return rows