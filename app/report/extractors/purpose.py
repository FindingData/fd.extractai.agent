from __future__ import annotations

from typing import Dict, List, Sequence

from langextract.core import data

from app.report.context import ReportContext
from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.examples.report_examples import EXAMPLES_BY_TYPE
from app.report.extractors.aware import ReportTypeAwareExtractor


class PurposeExtractor(ReportTypeAwareExtractor):
    slug = "purpose"
    target_slice_key = "letter_to_client"
    prompt_filename = "purpose.txt"

    fallback_examples = GENERAL_EXAMPLES["purpose"]

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        if report_type in ("house", "land", "asset"):
            return EXAMPLES_BY_TYPE[report_type]["purpose"]
        return ()

    def get_input_text(self, context: ReportContext) -> str:
        """
        ✅ 强化：优先取 letter_to_client 切片；
        若不存在（土地/资产常见），回退到全文前一段。
        """
        try:
            return super().get_input_text(context)
        except KeyError:
            md = context.ensure_markdown()
            # 只取前面一截，避免把全文塞进去导致跑偏
            return (md or "")[:4000]

    def post_process(self, annotated_doc, *, context: ReportContext) -> List[Dict]:
        rows = super().post_process(annotated_doc, context=context)
        for row in rows:
            row.setdefault("purpose", "")
            row.setdefault("usage", "")
            row.setdefault("report_type", (context.metadata or {}).get("report_type"))
        return rows