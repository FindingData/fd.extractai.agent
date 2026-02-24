from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Sequence

import langextract as lx
from langextract.core import data

from app.report.context import ReportContext, ReportSection
from config import CONFIG

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class Extractor(ABC):
    """Shared LangExtract wiring for every semantic extractor."""

    slug: str
    target_slice_key: str
    prompt_filename: str
    examples: Sequence[data.ExampleData]

    def __init__(
        self,
        *,
        model_id: Optional[str] = None,
        model_url: Optional[str] = None,
        max_char_buffer: int = 8192,
        num_ctx: int = 18000,
        timeout: int = 10 * 60,
    ) -> None:
        self.model_id = model_id or CONFIG.LOCAL_MODEL_NAME
        self.model_url = model_url or CONFIG.LOCAL_MODEL_URL
        self.max_char_buffer = max_char_buffer
        self.num_ctx = num_ctx
        self.timeout = timeout

    def __call__(self, context: ReportContext) -> List[dict]:
        text = self.get_input_text(context)
        if not text.strip():
            return []
        doc = self.run_langextract(text)
        return self.post_process(doc)

    def load_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_filename
        return prompt_path.read_text(encoding="utf-8")

    def run_langextract(self, text: str):
        prompt = self.load_prompt()
        return lx.extract(
            text,
            prompt_description=prompt,
            examples=self.examples or [],
            model_id=self.model_id,
            model_url=self.model_url,
            max_char_buffer=self.max_char_buffer,
            language_model_params={
                "num_ctx": self.num_ctx,
                "timeout": self.timeout,
            },
        )

    def get_input_text(self, context: ReportContext) -> str:
        if self.target_slice_key == "__full__":
            return context.ensure_markdown()
        slices = context.get_slices(self.target_slice_key)
        if not slices:
            raise KeyError(f"Slice '{self.target_slice_key}' not found for extractor '{self.slug}'.")
        if len(slices) == 1:
            return slices[0].text
        joined = "\n\n".join(f"### {s.title or self.target_slice_key}\n{s.text}" for s in slices)
        return joined

    def post_process(self, annotated_doc) -> List[dict]:
        extractions = getattr(annotated_doc, "extractions", None) or []
        rows: List[dict] = []
        for extraction in extractions:
            attrs = getattr(extraction, "attributes", None)
            if isinstance(attrs, dict) and attrs:
                rows.append(attrs)
        return rows
