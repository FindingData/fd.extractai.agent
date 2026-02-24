from __future__ import annotations

from typing import Dict, List

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.extractors.base import Extractor


class MethodExtractor(Extractor):
    slug = "method"
    target_slice_key = "__full__"
    prompt_filename = "method.txt"
    examples = GENERAL_EXAMPLES["method"]

    def post_process(self, annotated_doc) -> List[Dict]:
        rows = super().post_process(annotated_doc)
        for row in rows:
            weight = row.get("weight")
            if isinstance(weight, str):
                try:
                    row["weight"] = float(weight)
                except ValueError:
                    row["weight"] = None
        return rows

