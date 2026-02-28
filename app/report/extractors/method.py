from __future__ import annotations

from typing import Dict, List, Sequence

from langextract.core import data

from app.report.context import ReportContext
from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.examples.report_examples import EXAMPLES_BY_TYPE
from app.report.extractors.aware import ReportTypeAwareExtractor


class MethodExtractor(ReportTypeAwareExtractor):
    slug = "method"
    target_slice_key = "__full__"
    prompt_filename = "method.txt"

    fallback_examples = GENERAL_EXAMPLES["method"]

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        if report_type in ("house", "land", "asset"):
            return EXAMPLES_BY_TYPE[report_type]["method"]
        return ()

    def post_process(self, annotated_doc, *, context: ReportContext) -> List[Dict]:
        rows = super().post_process(annotated_doc, context=context)
        for row in rows:
            # 常见字段：weight / final_weight / final_method
            for k in ("weight", "final_weight"):
                v = row.get(k)
                if isinstance(v, str):
                    try:
                        row[k] = float(v)
                    except ValueError:
                        row[k] = None

            row.setdefault("report_type", (context.metadata or {}).get("report_type"))
        return rows