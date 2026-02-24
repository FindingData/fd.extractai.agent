from __future__ import annotations

from typing import Dict, List

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.extractors.base import Extractor


class AssumptionsExtractor(Extractor):
    slug = "assumptions"
    target_slice_key = "__full__"
    prompt_filename = "assumptions.txt"
    examples = GENERAL_EXAMPLES["assumptions"]

    def post_process(self, annotated_doc) -> List[Dict]:
        rows = super().post_process(annotated_doc)
        for row in rows:
            row["category"] = row.get("category") or "重要假设"
        return rows

