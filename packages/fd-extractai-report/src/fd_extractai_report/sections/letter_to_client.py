from __future__ import annotations

from typing import Iterable

from fd_extractai_report.context import ReportContext, ReportSection
from fd_extractai_report.sections.base import SectionSlicer


LETTER_SECTION_CONFIG = {
    "letter_to_client": [
        "致委托方函",
        "致函",
        "致客户函",
        "致委托人函",
    ]
}


class LetterToClientSlicer(SectionSlicer):
    """Slice out the letter-to-client block for downstream purpose/extractor usage."""

    def __init__(self) -> None:
        super().__init__(key="letter_to_client")

    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        grouped = context.slice_by_config(LETTER_SECTION_CONFIG)
        sections = grouped.get(self.key, [])
        if not sections and context.markdown_text:
            # Fallback: take first 600 chars as pseudo-letter.
            snippet = context.markdown_text[:600]
            sections = [
                ReportSection(
                    key=self.key,
                    title="致函（fallback）",
                    text=snippet,
                    metadata={"fallback": True},
                )
            ]
        return sections

