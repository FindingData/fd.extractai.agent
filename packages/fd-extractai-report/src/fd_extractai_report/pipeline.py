from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Literal

from fd_extractai_report.context import ReportContext, ReportSection
from fd_extractai_report.detectors import ReportTypeDetector, BaseDetector
from fd_extractai_report.converters import convert_word_to_md

# ⚠️ 注意：不要在这里 import 旧 slicer/extractor。
# 你现在的主线是 ruleset + RuleEngineSlicer / RuleEngineExtractorRunner。
# 旧类如果保留，也应该在 _build_default_components() 内部按需惰性 import。


# ============================================================
# Converters
# ============================================================

class MarkdownFileConverter:
    def convert(self, source_path: Path) -> str:
        return convert_word_to_md(str(source_path))


# ============================================================
# Result / Debug
# ============================================================

@dataclass
class PipelineResult:
    context: ReportContext
    outputs: Dict[str, List[dict]]
    evaluations: List[dict]
    warnings: List[str] = field(default_factory=list)


# ============================================================
# Benchmark
# ============================================================

class BenchmarkEvaluator:
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
        registry = {getattr(extractor, "slug", ""): extractor for extractor in extractors}
        results: List[dict] = []

        for bench in self.benchmarks:
            slug = bench.get("extractor_slug")
            extractor = registry.get(slug)
            if not extractor:
                continue

            ctx = ReportContext()
            ctx.set_markdown(bench["input_md"])

            # benchmark：直接塞 slice，避免 slicer 干扰
            target_key = getattr(extractor, "target_slice_key", "__full__")
            if target_key != "__full__":
                ctx.add_slice(
                    ReportSection(
                        key=target_key,
                        title=f"{bench.get('name','')}#{slug}",
                        text=bench["input_md"],
                        metadata={"benchmark": True},
                    )
                )

            actual = extractor(ctx) or []
            expected = bench.get("expected", []) or []
            matched = self._count_matches(actual, expected)

            results.append(
                {
                    "name": bench.get("name", ""),
                    "extractor": slug,
                    "matched": matched,
                    "expected": len(expected),
                    "passed": matched == len(expected),
                }
            )
        return results

    @staticmethod
    def _count_matches(actual: List[dict], expected: List[dict]) -> int:
        def is_subset(a: dict, e: dict) -> bool:
            return all(a.get(k) == v for k, v in e.items())

        count = 0
        for exp in expected:
            if any(is_subset(act, exp) for act in actual):
                count += 1
        return count


# ============================================================
# Validators
# ============================================================

class BaseValidator:
    def __call__(self, outputs: Dict[str, List[dict]]) -> List[str]:
        return []


# ============================================================
# Pipeline
# ============================================================

RunStage = Literal["load", "detect", "slice", "extract", "validate", "benchmark", "all"]


class ReportPipeline:
    """
    目标：让 batch 脚本安全调用：
      ctx = pipe.load(...)
      rt  = pipe.step_detect_report_type(ctx,...)
      pipe.step_slice(ctx,...)      # 可空
      outputs = pipe.step_extract(...)  # 可空

    重要：如果你传 slicers=[] / extractors=[]，绝对不能因为默认 import 而崩。
    """

    def __init__(
        self,
        *,
        converter: Optional[MarkdownFileConverter] = None,
         type_detector: Optional[BaseDetector] = None,
        slicers: Optional[Sequence[Any]] = None,
        extractors: Optional[Sequence[Any]] = None,
        evaluator: Optional[BenchmarkEvaluator] = None,
        validators: Optional[Sequence[BaseValidator]] = None,
    ) -> None:
        self.converter = converter or MarkdownFileConverter()
        self.type_detector = type_detector or ReportTypeDetector()
        self.evaluator = evaluator or BenchmarkEvaluator()
        self.validators = list(validators) if validators is not None else []

        # ✅ 关键：只在“完全没传”时才构造默认组件
        if slicers is None and extractors is None:
            self.slicers, self.extractors = self._build_default_components()
        else:
            self.slicers = list(slicers) if slicers is not None else []
            self.extractors = list(extractors) if extractors is not None else []

    def _build_default_components(self) -> tuple[list[Any], list[Any]]:
        """
        惰性构造默认 slicers/extractors（仅当你没传时）。
        如果你现在要彻底切换到 ruleset 体系，可以把这里直接返回空列表。
        """
        try:        
            slicers = []
            extractors = []
            return slicers, extractors
        except Exception:
            # ✅ 保底：不要因为默认组件缺失影响批处理
            return [], []

    def _log(self, msg: str, debug: bool = True) -> None:
        if debug:
            print(f"  {msg}")

    # -------------------------
    # Load
    # -------------------------
    def load(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        context: Optional[ReportContext] = None,
        debug: bool = False,
    ) -> ReportContext:
        if context is not None:
            return context

        if debug:
            source = str(docx_path) if docx_path else "Markdown Text"
            print(f"🚀 [LOAD] source={source}")

        start_time = time.time()

        path_obj = Path(docx_path).resolve() if docx_path else None
        ctx = ReportContext(source_path=path_obj)

        if path_obj is not None:
            md_text = self.converter.convert(path_obj) or ""
            self._log(f"📄 DOCX->MD done chars={len(md_text)}", debug)
        else:
            md_text = markdown_text or ""

        ctx.set_markdown(md_text)
        self._log(f"⏱ load cost={time.time() - start_time:.2f}s", debug)
        return ctx

    # -------------------------
    # Detect
    # -------------------------
    def step_detect_report_type(
        self,
        context: ReportContext,
        *,
        head_chars: int = 2000,
        debug: bool = False,
    ) -> str:
        md = context.ensure_markdown() or ""
        res = self.type_detector.detect(md, head_chars=head_chars)        
        rt = res.report_type        
        info = res.info or {}
        context.set_metadata(report_type=rt, report_type_debug=info, report_type_confidence=res.confidence)

        if debug:
            mode = (info or {}).get("mode")
            reason = (info or {}).get("reason")
            if mode == "strong":
                print(f"🧠 detect report_type={rt} mode=strong hit={info.get('strong_text')} reason={reason}")
            else:
                print(f"🧠 detect report_type={rt} mode={mode} scores={info.get('scores')} reason={reason} conf={res.confidence}")
        return rt

    # -------------------------
    # Slice
    # -------------------------
    def step_slice(self, context: ReportContext, debug: bool = False) -> ReportContext:
        if debug:
            print("✂️  [SLICE] start ...")

        start_time = time.time()
        context.ensure_markdown()

        for slicer in self.slicers:
            name = slicer.__class__.__name__
            slicer(context)
            self._log(f"🔹 slicer done: {name}", debug)

        total_slices = sum(len(v) for v in (context.slices or {}).values())
        self._log(f"✅ slice done total_slices={total_slices} cost={time.time() - start_time:.2f}s", debug)
        return context

    # -------------------------
    # Extract (旧模式：基于 self.extractors)
    # 你现在主线是 ruleset runner，这个方法仍保留兼容，不影响 batch 用 pipe.load/detect。
    # -------------------------
    def step_extract(
        self,
        context: ReportContext,
        *,
        slice_only: bool = True,
        empty_if_missing_slice: bool = True,
        debug: bool = False,
        max_slice_chars: int = 12000,
    ) -> Dict[str, List[dict]]:
        if debug:
            mode = "slice_only" if slice_only else "full"
            print(f"🧠 [EXTRACT] start mode={mode}")

        start_time = time.time()

        # 没有 extractors 就直接返回空（批处理时经常这么用）
        if not self.extractors:
            self._log("⚠️ no extractors configured, skip", debug)
            return {}

        inputs = self._prepare_extractor_inputs(
            context,
            slice_only=slice_only,
            empty_if_missing_slice=empty_if_missing_slice,
            debug=debug,
            max_slice_chars=max_slice_chars,
        )

        outputs: Dict[str, List[dict]] = {}
        registry = {ex.slug: ex for ex in self.extractors}

        for slug, in_ctx in inputs.items():
            ex_start = time.time()
            if in_ctx is None:
                outputs[slug] = []
                self._log(f"⚠️ skip {slug}: missing slice", debug)
                continue

            results = registry[slug](in_ctx) or []
            outputs[slug] = results
            self._log(f"✨ extracted {slug}: rows={len(results)} cost={time.time() - ex_start:.2f}s", debug)

        self._log(f"⏱ extract cost={time.time() - start_time:.2f}s", debug)
        return outputs

    def _prepare_extractor_inputs(
        self,
        context: ReportContext,
        *,
        slice_only: bool,
        empty_if_missing_slice: bool,
        debug: bool,
        max_slice_chars: int,
    ) -> Dict[str, Optional[ReportContext]]:
        inputs: Dict[str, Optional[ReportContext]] = {}

        for extractor in self.extractors:
            slug = extractor.slug
            target_key = getattr(extractor, "target_slice_key", "__full__")

            if not slice_only or target_key == "__full__":
                inputs[slug] = context
                continue

            slices = context.get_slices(target_key)
            if not slices:
                if debug:
                    self._log(f"🔍 input {slug}: missing slice {target_key}", debug)
                inputs[slug] = None if empty_if_missing_slice else context
                continue

            slice_text = "\n\n".join((s.text or "") for s in slices if s).strip()
            if not slice_text:
                inputs[slug] = None
                continue

            if max_slice_chars and len(slice_text) > max_slice_chars:
                slice_text = slice_text[:max_slice_chars]

            tmp_ctx = ReportContext(source_path=context.source_path)
            tmp_ctx.set_markdown(slice_text)
            if context.metadata:
                tmp_ctx.set_metadata(**context.metadata)
            for s in slices:
                tmp_ctx.add_slice(s)

            inputs[slug] = tmp_ctx

        return inputs

    # -------------------------
    # Validate
    # -------------------------
    def validate(self, outputs: Dict[str, List[dict]], debug: bool = False) -> List[str]:
        if debug:
            print("⚖️  [VALIDATE] start ...")

        warnings: List[str] = []
        for v in self.validators:
            name = v.__class__.__name__
            try:
                current = v(outputs) or []
                if debug and current:
                    self._log(f"❗ {name} warnings={len(current)}", debug)
                warnings.extend(current)
            except Exception as e:
                warnings.append(f"⚠️ validator error {name}: {e}")

        if debug and not warnings:
            self._log("🟢 validate ok", debug)
        return warnings

    # -------------------------
    # Benchmark (补齐)
    # -------------------------
    def step_benchmark(self) -> List[dict]:
        return self.evaluator.evaluate(self.extractors)

    # -------------------------
    # Run / Run until
    # -------------------------
    def run(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        slice_only: bool = True,
        want_benchmark: bool = False,
        debug: bool = False,
    ) -> PipelineResult:
        if debug:
            print("\n" + "=" * 60)
            print("🏁 ReportPipeline run")
            print("=" * 60)

        t0 = time.time()

        ctx = self.load(docx_path=docx_path, markdown_text=markdown_text, debug=debug)
        self.step_detect_report_type(ctx, debug=debug)
        self.step_slice(ctx, debug=debug)
        outputs = self.step_extract(ctx, slice_only=slice_only, debug=debug)
        warnings = self.validate(outputs, debug=debug)

        evaluations: List[dict] = []
        if want_benchmark:
            evaluations = self.step_benchmark()

        if debug:
            print("-" * 60)
            print(f"🎉 done cost={time.time() - t0:.2f}s warnings={len(warnings)} eval={len(evaluations)}")
            print("=" * 60 + "\n")

        return PipelineResult(context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings)

    def run_until(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        until: RunStage = "all",
        slice_only: bool = True,
        want_benchmark: bool = False,
        debug: bool = False,
    ):
        ctx = self.load(docx_path=docx_path, markdown_text=markdown_text, debug=debug)
        if until == "load":
            return ctx

        self.step_detect_report_type(ctx, debug=debug)
        if until == "detect":
            return ctx

        self.step_slice(ctx, debug=debug)
        if until == "slice":
            return ctx

        outputs = self.step_extract(ctx, slice_only=slice_only, debug=debug)
        if until == "extract":
            return ctx, outputs

        warnings = self.validate(outputs, debug=debug)
        if until == "validate":
            return ctx, outputs, warnings

        evaluations: List[dict] = []
        if want_benchmark or until in ("benchmark", "all"):
            evaluations = self.step_benchmark()

        return PipelineResult(context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings)