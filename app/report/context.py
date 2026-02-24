from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.utils.markdown_utils import bucket_by_targets, sectionize


@dataclass
class ReportSection:
    """Normalized block of text that can be routed to extractors."""

    key: str
    title: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **extra: Any) -> "ReportSection":
        merged = {**self.metadata, **extra}
        return ReportSection(key=self.key, title=self.title, text=self.text, metadata=merged)


@dataclass
class ReportContext:
    """
    Holds lifecycle data for a report as it goes through convert -> slice -> extract -> eval.
    """

    source_path: Optional[Path] = None
    markdown_text: Optional[str] = None
    slices: Dict[str, List[ReportSection]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def ensure_markdown(self) -> str:
        if not self.markdown_text:
            raise ValueError("Markdown content is required before slicing.")
        return self.markdown_text

    def set_markdown(self, markdown: str) -> None:
        self.markdown_text = markdown

    def set_metadata(self, **extra: Any) -> None:
        self.metadata.update(extra)

    def add_slice(self, section: ReportSection) -> None:
        self.slices.setdefault(section.key, []).append(section)

    def get_slice(self, key: str) -> Optional[ReportSection]:
        slices = self.slices.get(key) or []
        return slices[0] if slices else None

    def get_slices(self, key: str) -> List[ReportSection]:
        return list(self.slices.get(key) or [])

    def slice_by_config(self, config: Dict[str, List[str]]) -> Dict[str, List[ReportSection]]:
        md_text = self.ensure_markdown()
        sections = sectionize(md_text)
        grouped = bucket_by_targets(sections, config)
        normalized: Dict[str, List[ReportSection]] = {}
        for key, raw_sections in grouped.items():
            normalized[key] = [
                ReportSection(
                    key=key,
                    title=raw["title"],
                    text=raw["content"],
                    metadata={"level": raw["level"]},
                )
                for raw in raw_sections
            ]
        return normalized

    def iter_slices(self) -> Iterable[ReportSection]:
        for slices in self.slices.values():
            for section in slices:
                yield section
