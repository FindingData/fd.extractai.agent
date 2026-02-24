from __future__ import annotations

from typing import Dict, List

from app.report.examples.valuation_examples import VALUATION_EXAMPLES
from app.report.extractors.base import Extractor


class ValuationExtractor(Extractor):
    slug = "valuation"
    target_slice_key = "valuation_tables"
    prompt_filename = "valuation.txt"
    examples = VALUATION_EXAMPLES

    def post_process(self, annotated_doc) -> List[Dict]:
        rows = super().post_process(annotated_doc)
        for row in rows:
            row["building_area"] = self._to_number(row.get("building_area"))
            row["unit_price"] = self._to_number(row.get("unit_price"))
            row["total_price"] = self._to_number(row.get("total_price"))
        return rows

    @staticmethod
    def _to_number(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value) if float(value).is_integer() else float(value)
        if isinstance(value, str):
            digits = "".join(ch for ch in value if (ch.isdigit() or ch in ".-"))
            try:
                if not digits:
                    return None
                num = float(digits)
                return int(num) if num.is_integer() else num
            except ValueError:
                return None
        return None
