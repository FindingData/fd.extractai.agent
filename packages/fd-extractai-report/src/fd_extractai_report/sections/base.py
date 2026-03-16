from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Sequence

from fd_extractai_report.context import ReportContext, ReportSection


class SectionSlicer(ABC):
    """Extracts a well-defined portion of the markdown and registers it on the context."""

    key: str

    def __init__(self, key: str) -> None:
        self.key = key

    def __call__(self, context: ReportContext) -> Sequence[ReportSection]:
        slices = list(self.slice(context))        
        return slices

    @abstractmethod
    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        """Return the slices produced by this slicer."""


def ensure_slice(context: ReportContext, key: str) -> ReportSection:
    section = context.get_slice(key)
    if not section:
        raise KeyError(f"Section slice '{key}' is required before extraction.")
    return section

