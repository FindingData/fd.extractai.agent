from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import langextract as lx
from langextract.core import data

from app.report.context import ReportContext
from config import CONFIG

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

ExampleSpec = Union[
    Sequence[data.ExampleData],                     # 直接给 list/tuple
    Mapping[str, Sequence[data.ExampleData]],       # {"house":[...], "fallback":[...]}
]


@dataclass
class ExtractorSpec:
    """
    配置驱动的抽取任务定义（可选使用）。
    你可以继续写子类；也可以只用 spec 来构造一个 Extractor 实例。
    """
    slug: str
    prompt_filename: str

    # 输入来源：支持多个切片合并；默认全文
    input_slice_keys: List[str] = field(default_factory=lambda: ["__full__"])

    # 切片缺失时怎么处理： "empty" | "full" | "raise"
    missing_slice_policy: str = "empty"

    # examples：支持按 report_type 选择 + fallback
    examples: ExampleSpec = field(default_factory=tuple)

    # 输出通用后处理：补默认值/注入 context 字段
    defaults: Dict[str, Any] = field(default_factory=dict)
    inject_context_fields: List[str] = field(default_factory=list)

    # 输入合并时是否加标题
    add_titles: bool = True

    # 输入最大长度
    max_input_chars: int = 12000


class Extractor(ABC):
    """Shared LangExtract wiring for every semantic extractor."""

    # --- 旧接口：保持兼容 ---
    slug: str
    target_slice_key: str = "__full__"
    prompt_filename: str

    # examples 可以是 list，也可以是 {"house":..., "fallback":...}
    examples: ExampleSpec = ()

    # --- 新能力：默认不开启，不影响旧子类 ---
    input_slice_keys: Optional[List[str]] = None     # 若不设，回退到 target_slice_key
    missing_slice_policy: str = "empty"              # "empty" | "full" | "raise"
    add_titles: bool = True
    max_input_chars: int = 12000

    defaults: Dict[str, Any] = {}
    inject_context_fields: List[str] = []

    def __init__(
        self,
        *,
        model_id: Optional[str] = None,
        model_url: Optional[str] = None,
        max_char_buffer: int = 8192,
        num_ctx: int = 18000,
        timeout: int = 10 * 60,
        spec: Optional[ExtractorSpec] = None,        # ✅ 可选：配置驱动
    ) -> None:
        self.model_id = model_id or CONFIG.LOCAL_MODEL_NAME
        self.model_url = model_url or CONFIG.LOCAL_MODEL_URL
        self.max_char_buffer = max_char_buffer
        self.num_ctx = num_ctx
        self.timeout = timeout

        # ✅ 如果传了 spec，用 spec 覆盖（用于“动态配置，不写子类”）
        self._spec = spec
        if spec is not None:
            self.slug = spec.slug
            self.prompt_filename = spec.prompt_filename
            self.input_slice_keys = spec.input_slice_keys
            self.missing_slice_policy = spec.missing_slice_policy
            self.examples = spec.examples
            self.defaults = spec.defaults
            self.inject_context_fields = spec.inject_context_fields
            self.add_titles = spec.add_titles
            self.max_input_chars = spec.max_input_chars

    def __call__(self, context: ReportContext) -> List[dict]:
        text = self.get_input_text(context)
        if not text.strip():
            return []

        doc = self.run_langextract(text, context=context)
        return self.post_process(doc, context=context)

    def load_prompt(self) -> str:
        prompt_path = PROMPTS_DIR / self.prompt_filename
        return prompt_path.read_text(encoding="utf-8")

    # ✅ 支持 report_type-aware examples
    def get_examples(self, context: ReportContext) -> Sequence[data.ExampleData]:
        ex = self.examples or ()
        if isinstance(ex, Mapping):
            rt = (context.metadata or {}).get("report_type")
            if rt and rt in ex and ex[rt]:
                return ex[rt]
            return ex.get("fallback", ()) or ()
        return ex

    def run_langextract(self, text: str, *, context: ReportContext):
        prompt = self.load_prompt()
        examples = self.get_examples(context)

        return lx.extract(
            text,
            prompt_description=prompt,
            examples=list(examples) if examples else [],
            model_id=self.model_id,
            model_url=self.model_url,
            max_char_buffer=self.max_char_buffer,
            language_model_params={
                "num_ctx": self.num_ctx,
                "timeout": self.timeout,
            },
        )

    # ✅ 多切片输入 + 缺失策略 + 向后兼容 target_slice_key
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