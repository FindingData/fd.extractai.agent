from __future__ import annotations

from typing import Dict, List, Sequence

from langextract.core import data

from app.report.context import ReportContext
from app.report.examples.valuation_examples import VALUATION_EXAMPLES
from app.report.examples.report_examples import EXAMPLES_BY_TYPE
from app.report.extractors.aware import ReportTypeAwareExtractor


class ValuationExtractor(ReportTypeAwareExtractor):
    slug = "valuation"
    target_slice_key = "valuation_tables"
    prompt_filename = "valuation.txt"

    # ✅ 兜底：如果 report_type 未识别，仍可用你原来的房产表格例子
    fallback_examples = VALUATION_EXAMPLES

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        if report_type in ("house", "land", "asset"):
            return EXAMPLES_BY_TYPE[report_type]["targets"]
        return ()

    def post_process(self, annotated_doc, *, context: ReportContext) -> List[Dict]:
        rows = super().post_process(annotated_doc, context=context)
        rt = (context.metadata or {}).get("report_type")

        for row in rows:
            # ✅ 常见数值字段统一转 number（房产）
            for k in ("building_area", "unit_price", "total_price"):
                if k in row:
                    row[k] = self._to_number(row.get(k))

            # ✅ 土地常见字段
            for k in ("land_area", "plot_ratio", "lease_years"):
                if k in row:
                    row[k] = self._to_number(row.get(k))

            # ✅ 资产常见字段
            for k in ("quantity", "book_value", "assessed_value"):
                if k in row:
                    row[k] = self._to_number(row.get(k))

            row.setdefault("report_type", rt)

        return rows

    @staticmethod
    def _to_number(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value) if float(value).is_integer() else float(value)
        if isinstance(value, str):
            # 去掉千分位、单位、中文等，只保留数字/./-
            digits = "".join(ch for ch in value if (ch.isdigit() or ch in ".-"))
            try:
                if not digits:
                    return None
                num = float(digits)
                return int(num) if num.is_integer() else num
            except ValueError:
                return None
        return None