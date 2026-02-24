from __future__ import annotations

from typing import Dict, List

from app.report.examples.general_examples import GENERAL_EXAMPLES
from app.report.extractors.base import Extractor


class PurposeExtractor(Extractor):
    slug = "purpose"
    target_slice_key = "letter_to_client"
    prompt_filename = "purpose.txt"
    examples = GENERAL_EXAMPLES["purpose"]

    def post_process(self, annotated_doc) -> List[Dict]:
        rows = super().post_process(annotated_doc)
        for row in rows:
            row.setdefault("purpose", "")
            row.setdefault("usage", "")
        return rows

