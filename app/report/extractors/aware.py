from __future__ import annotations

from typing import Sequence

from langextract.core import data

from app.report.context import ReportContext
from app.report.extractors.base import Extractor


class ReportTypeAwareExtractor(Extractor):
    """
    让 extractor 支持按 context.metadata['report_type'] 选择 examples。
    子类只需要实现 get_examples_for_type。
    """

    fallback_examples: Sequence[data.ExampleData] = ()

    def get_examples(self, context: ReportContext) -> Sequence[data.ExampleData]:
        rt = (context.metadata or {}).get("report_type")
        examples = self.get_examples_for_type(rt)
        return examples or self.fallback_examples or self.examples or ()

    def get_examples_for_type(self, report_type: str | None) -> Sequence[data.ExampleData]:
        return ()