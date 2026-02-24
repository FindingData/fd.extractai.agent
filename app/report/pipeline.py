from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Any

from app.report.context import ReportContext, ReportSection
from app.report.extractors.assumptions import AssumptionsExtractor
from app.report.extractors.conclusion import ConclusionExtractor
from app.report.extractors.method import MethodExtractor
from app.report.extractors.purpose import PurposeExtractor
from app.report.extractors.valuation import ValuationExtractor
from app.report.sections.letter_to_client import LetterToClientSlicer
from app.report.sections.valuation_tables import ValuationTablesSlicer
from app.utils.text_utils import convert_docx_to_md


class MarkdownFileConverter:
    """Convert DOCX report into Markdown using shared utility."""

    def convert(self, source_path: Path) -> str:
        return convert_docx_to_md(str(source_path))


class PassthroughConverter:
    """Use when upstream caller already provides Markdown."""

    def __init__(self, markdown_text: str):
        self.markdown_text = markdown_text

    def convert(self, _source_path: Optional[Path] = None) -> str:
        return self.markdown_text


@dataclass
class PipelineResult:
    context: ReportContext
    outputs: Dict[str, List[dict]]
    evaluations: List[dict]


@dataclass
class StepDebug:
    """给批处理/调试监控用的轻量信息（可选用）"""
    slice_stats: Dict[str, int]
    outputs_stats: Dict[str, int]


class BenchmarkEvaluator:
    """Lightweight JSON benchmark harness to sanity-check extractors."""

    def __init__(self, benchmark_dir: Optional[Path] = None) -> None:
        self.benchmark_dir = benchmark_dir or Path(__file__).resolve().parents[1] / "benchmarks"
        self.benchmarks = self._load_benchmarks()

    def _load_benchmarks(self) -> List[dict]:
        benches: List[dict] = []
        if not self.benchmark_dir.exists():
            return benches
        for path in sorted(self.benchmark_dir.glob("benchmark_*.json")):
            try:
                benches.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return benches

    def evaluate(self, extractors: Sequence) -> List[dict]:
        if not self.benchmarks:
            return []
        registry = {extractor.slug: extractor for extractor in extractors}
        results = []
        for bench in self.benchmarks:
            slug = bench.get("extractor_slug")
            extractor = registry.get(slug)
            if not extractor:
                continue
            ctx = ReportContext()
            ctx.set_markdown(bench["input_md"])

            # 注意：benchmark 这里是“extractor 单测”，直接塞 slice，避免 slicer 干扰
            if getattr(extractor, "target_slice_key", "__full__") != "__full__":
                ctx.add_slice(
                    ReportSection(
                        key=extractor.target_slice_key,
                        title=f"{bench['name']}#{slug}",
                        text=bench["input_md"],
                        metadata={"benchmark": True},
                    )
                )

            actual = extractor(ctx)
            matched = self._count_matches(actual, bench["expected"])
            results.append(
                {
                    "name": bench["name"],
                    "extractor": slug,
                    "matched": matched,
                    "expected": len(bench["expected"]),
                    "passed": matched == len(bench["expected"]),
                }
            )
        return results

    @staticmethod
    def _count_matches(actual: List[dict], expected: List[dict]) -> int:
        count = 0
        for exp in expected:
            if any(BenchmarkEvaluator._is_subset(act, exp) for act in actual):
                count += 1
        return count

    @staticmethod
    def _is_subset(actual: dict, expected: dict) -> bool:
        return all(actual.get(k) == v for k, v in expected.items())


class ReportPipeline:
    """
    支持两种使用方式：
    A) 一键：run() = convert -> slice -> extract -> benchmark
    B) 分步：step_convert / step_slice / step_extract / step_benchmark
    """

    def __init__(
        self,
        *,
        converter: Optional[MarkdownFileConverter] = None,
        slicers: Optional[Sequence] = None,
        extractors: Optional[Sequence] = None,
        evaluator: Optional[BenchmarkEvaluator] = None,
    ) -> None:
        self.converter = converter or MarkdownFileConverter()
        self.slicers = slicers or [
            LetterToClientSlicer(),
            ValuationTablesSlicer(),
        ]
        self.extractors = extractors or [
            ValuationExtractor(),
            PurposeExtractor(),
            AssumptionsExtractor(),
            MethodExtractor(),
            ConclusionExtractor(),
        ]
        self.evaluator = evaluator or BenchmarkEvaluator()

    # -------------------------
    # Step 1: Convert
    # -------------------------
    def step_convert(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        context: Optional[ReportContext] = None,
    ) -> ReportContext:
        """
        只负责：拿到 markdown 并写入 context.markdown_text
        """
        if not docx_path and not markdown_text:
            raise ValueError("docx_path or markdown_text must be provided.")

        path_obj = Path(docx_path) if docx_path else None
        ctx = context or ReportContext(source_path=path_obj)
        if path_obj:
            ctx.source_path = path_obj

        if docx_path:
            md_text = self.converter.convert(path_obj)
        else:
            md_text = markdown_text or ""

        ctx.set_markdown(md_text)
        return ctx

    # -------------------------
    # Step 2: Slice
    # -------------------------
    def step_slice(self, context: ReportContext) -> ReportContext:
        """
        只负责：运行 slicers，填充 context.slices
        """
        context.ensure_markdown()
        for slicer in self.slicers:
            slicer(context)
        return context

    # -------------------------
    # Step 3: Extract
    # -------------------------
    def step_extract(
        self,
        context: ReportContext,
        *,
        slice_only: bool = True,
        empty_if_missing_slice: bool = True,
        debug: bool = False,
        max_slice_chars: int = 12000,  # 防止切片仍然太大
    ) -> Dict[str, List[dict]]:
        outputs: Dict[str, List[dict]] = {}

        for extractor in self.extractors:
            slug = extractor.slug
            target_key = getattr(extractor, "target_slice_key", "__full__")

            # 1) slice_only 模式：禁止 __full__（除非你明确允许）
            if slice_only and target_key == "__full__":
                if debug:
                    print(f"[EXTRACT][SKIP] {slug} target_key=__full__ (slice_only=True)")
                outputs[slug] = []
                continue

            # 2) 取切片
            if slice_only:
                slices = context.get_slices(target_key)
                if not slices:
                    if debug:
                        print(f"[EXTRACT][MISS] {slug} slice_key={target_key} (0 slices)")
                    outputs[slug] = [] if empty_if_missing_slice else (extractor(context) or [])
                    continue

                # ✅ 核心：只拼接切片文本作为输入，不给全文
                slice_text = "\n\n".join(s.text for s in slices if s and s.text)
                if not slice_text.strip():
                    outputs[slug] = []
                    continue

                # 防止仍然太大导致卡住
                if len(slice_text) > max_slice_chars:
                    slice_text = slice_text[:max_slice_chars]

                tmp_ctx = ReportContext(source_path=context.source_path)
                tmp_ctx.set_markdown(slice_text)   # ✅ 只给切片
                # 同时把切片挂上（给 extractor 用 ctx.get_slices）
                for s in slices:
                    tmp_ctx.add_slice(s)

                if debug:
                    print(
                        f"[EXTRACT] {slug} slice_key={target_key} "
                        f"slices={len(slices)} chars={len(slice_text)}"
                    )

                outputs[slug] = extractor(tmp_ctx) or []
                continue

            # 3) 非 slice_only（保留原行为）
            outputs[slug] = extractor(context) or []

        return outputs

    # -------------------------
    # Step 4: Benchmark
    # -------------------------
    def step_benchmark(self) -> List[dict]:
        return self.evaluator.evaluate(self.extractors) if self.evaluator else []

    # -------------------------
    # Debug helper（可选）
    # -------------------------
    def build_debug(self, context: ReportContext, outputs: Dict[str, List[dict]]) -> StepDebug:
        slice_stats = {k: len(v) for k, v in (context.slices or {}).items()}
        outputs_stats = {k: len(v or []) for k, v in (outputs or {}).items()}
        return StepDebug(slice_stats=slice_stats, outputs_stats=outputs_stats)

    # -------------------------
    # Backward-compatible run()
    # -------------------------
    def run(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        slice_only: bool = True,
    ) -> PipelineResult:
        """
        兼容旧用法，但内部按步骤走：
          convert -> slice -> extract -> benchmark
        """
        ctx = self.step_convert(docx_path=docx_path, markdown_text=markdown_text)
        self.step_slice(ctx)
        outputs = self.step_extract(ctx, slice_only=slice_only)
        evaluations = self.step_benchmark()
        return PipelineResult(context=ctx, outputs=outputs, evaluations=evaluations)