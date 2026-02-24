from __future__ import annotations

from typing import Dict, List

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.extractors.base import Extractor


class ConclusionExtractor(Extractor):
    slug = "conclusion"
    target_slice_key = "__full__"
    prompt_filename = "conclusion.txt"
    examples = GENERAL_EXAMPLES["conclusion"]

    def post_process(self, annotated_doc) -> List[Dict]:
        rows = super().post_process(annotated_doc)
        for row in rows:
            if date := row.get("value_date"):
                row["value_date"] = date.replace("年", "-").replace("月", "-").replace("日", "")
        return rows

