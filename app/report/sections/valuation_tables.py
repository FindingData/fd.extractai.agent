from __future__ import annotations

import re
from typing import Iterable, List

from app.report.context import ReportContext, ReportSection
from app.report.sections.base import SectionSlicer
from app.utils.markdown_utils import find_blocks_by_pattern


class ValuationTablesSlicer(SectionSlicer):
    """Collects table-heavy sections such as '估价对象一览表' and registers them."""

    TABLE_PATTERNS = [
        re.compile(r"估价(对象|结果).*(表|列表)", re.I),
        re.compile(r"估价瀵硅薄", re.I),
        re.compile(r"valuation", re.I),
    ]

    def __init__(self) -> None:
        super().__init__(key="valuation_tables")

    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        text = context.ensure_markdown()
        aggregated: List[ReportSection] = []
        for pattern in self.TABLE_PATTERNS:
            matches = find_blocks_by_pattern(text, pattern)
            for idx, match in enumerate(matches):
                aggregated.append(
                    ReportSection(
                        key=self.key,
                        title=match.get("title") or match.get("kind", "snippet"),
                        text=match["text"],
                        metadata={
                            "pattern": pattern.pattern,
                            "kind": match["kind"],
                            "match_index": idx,
                        },
                    )
                )
        if not aggregated:
            aggregated.append(
                ReportSection(
                    key=self.key,
                    title="全文",
                    text=text,
                    metadata={"fallback": True},
                )
            )
        return aggregated
