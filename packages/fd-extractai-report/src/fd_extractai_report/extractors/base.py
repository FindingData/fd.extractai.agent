# app/report/extractors/base.py  (你的 Extractor 所在文件)
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import langextract as lx
from langextract.core import data

from fd_extractai_report.context import ReportContext
from config import CONFIG
from fd_extractai_report.rules.extracting.schema import ExtractorSpec  # ✅ 只引用 spec（不再有 ExampleSpec）

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class Extractor:
    slug: str = ""
    target_slice_key: str = "__full__"
    prompt_filename: str = ""
    # ✅ 只保留“最终 examples”
    examples: Sequence[data.ExampleData] = ()
    input_slice_keys: Optional[List[str]] = None
    missing_slice_policy: str = "empty"
    add_titles: bool = True
    max_input_chars: int = 12000    
    def __init__(
        self,
        *,
        model_id: Optional[str] = None,
        model_url: Optional[str] = None,
        max_char_buffer: int = 8192,
        num_ctx: int = 18000,
        timeout: int = 10 * 60,
        spec: Optional[ExtractorSpec] = None,
        examples: Optional[Sequence[data.ExampleData]] = None,  # ✅ runner 解析后传进来
    ) -> None:
        self.model_id = model_id or CONFIG.LOCAL_MODEL_NAME
        self.model_url = model_url or CONFIG.LOCAL_MODEL_URL
        self.max_char_buffer = max_char_buffer
        self.num_ctx = num_ctx
        self.timeout = timeout

        self.defaults: Dict[str, Any] = {}
        self.inject_context_fields: List[str] = []

        self._spec = spec
        if spec is not None:
            self.slug = spec.slug
            self.prompt_filename = spec.prompt_filename
            self.input_slice_keys = list(spec.input_slice_keys or [])
            self.missing_slice_policy = spec.missing_slice_policy
            self.defaults = dict(spec.defaults or {})
            self.inject_context_fields = list(spec.inject_context_fields or [])
            self.add_titles = spec.add_titles
            self.max_input_chars = spec.max_input_chars

        # ✅ 最终 examples 入口：优先使用传入的 examples，否则用 self.examples
        if examples is not None:
            self.examples = list(examples)

    def __call__(self, context: ReportContext) -> List[dict]:
        text = self.get_input_text(context)
        if not text or not text.strip():
            return []        
        doc = self.run_langextract(text, context=context)
        return self.post_process(doc, context=context)
    
    def load_prompt(self) -> str:
        return (PROMPTS_DIR / self.prompt_filename).read_text(encoding="utf-8")

    def run_langextract(self, text: str, *, context: ReportContext):
        prompt = self.load_prompt()
        return lx.extract(
            text,
            prompt_description=prompt,
            examples=list(self.examples) if self.examples else [],
            model_id=self.model_id,
            model_url=self.model_url,
            max_char_buffer=self.max_char_buffer,
            language_model_params={"num_ctx": self.num_ctx, "timeout": self.timeout},
        )

    # get_input_text / _truncate / post_process 你原来的保持不动即可
    def get_input_text(self, context: ReportContext) -> str:
        keys = self.input_slice_keys
        if not keys:
            keys = [getattr(self, "target_slice_key", "__full__") or "__full__"]

        # 1) 包含全文：直接走全文（最简单、最稳）
        if "__full__" in keys:
            return self._truncate(context.ensure_markdown())

        # 2) 合并多个切片
        parts: List[str] = []
        for k in keys:
            slices = context.get_slices(k) or []
            if not slices:
                if self.missing_slice_policy == "raise":
                    raise KeyError(f"Slice '{k}' not found for extractor '{self.slug}'.")
                if self.missing_slice_policy == "full":
                    return self._truncate(context.ensure_markdown())
                continue  # empty：跳过

            if len(slices) == 1:
                parts.append(slices[0].text or "")
            else:
                if self.add_titles:
                    joined = "\n\n".join(
                        f"### {s.title or k}\n{s.text}" for s in slices if s and s.text
                    )
                else:
                    joined = "\n\n".join(s.text for s in slices if s and s.text)
                parts.append(joined)

        text = "\n\n".join(p for p in parts if p and p.strip())
        return self._truncate(text)

    def _truncate(self, text: str) -> str:
        if self.max_input_chars and len(text) > self.max_input_chars:
            return text[: self.max_input_chars]
        return text

    # ✅ 通用后处理：保留你原逻辑 + defaults + inject_context_fields
    def post_process(self, annotated_doc, *, context: ReportContext) -> List[dict]:
        extractions = getattr(annotated_doc, "extractions", None) or []
        rows: List[dict] = []

        rt = (context.metadata or {}).get("report_type")

        for extraction in extractions:
            attrs = getattr(extraction, "attributes", None)
            if not (isinstance(attrs, dict) and attrs):
                continue

            row = dict(attrs)

            # 1) defaults：空值兜底
            for k, v in (self.defaults or {}).items():
                if row.get(k) in (None, "", []):
                    row[k] = v

            # 2) inject context fields：常用把 report_type 带上
            for f in (self.inject_context_fields or []):
                if f == "report_type":
                    row.setdefault("report_type", rt)
                else:
                    if context.metadata and f in context.metadata:
                        row.setdefault(f, context.metadata.get(f))

            rows.append(row)

        return rows