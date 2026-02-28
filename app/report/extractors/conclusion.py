from __future__ import annotations

from typing import Dict, List, Sequence

from langextract.core import data

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.examples.report_examples import EXAMPLES_BY_TYPE
from app.report.extractors.aware import ReportTypeAwareExtractor
from app.report.context import ReportContext


class ConclusionExtractor(ReportTypeAwareExtractor):
    slug = "conclusion"
    target_slice_key = "__full__"
    prompt_filename = "conclusion.txt"

    fallback_examples = GENERAL_EXAMPLES["conclusion"]

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        if report_type in ("house", "land", "asset"):
            return EXAMPLES_BY_TYPE[report_type]["conclusion"]
        return ()

    def post_process(self, annotated_doc, *, context: ReportContext) -> List[Dict]:
        rows = super().post_process(annotated_doc, context=context)
        for row in rows:
            if date := row.get("value_date"):
                # 兼容 “2025年8月30日” / “2025-08-30”
                d = str(date)
                d = d.replace("年", "-").replace("月", "-").replace("日", "")
                d = d.replace("/", "-").strip()
                row["value_date"] = d
            row.setdefault("report_type", (context.metadata or {}).get("report_type"))
        return rows