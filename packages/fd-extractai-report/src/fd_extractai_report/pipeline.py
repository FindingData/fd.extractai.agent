from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Literal

from fd_extractai_report.sections.rule_engine_slicer import RuleEngineSlicer
from fd_extractai_report.extractors.rule_engine_extractor import (
    RuleEngineExtractorRunner,
)
from fd_extractai_report.rules.extracting.schema import ExtractRuleSet
from fd_extractai_report.context import ReportContext, ReportSection
from fd_extractai_report.detectors import ReportTypeDetector, BaseDetector
from fd_extractai_report.converters.markdown_converter import MarkdownFileConverter
from fd_extractai_report.settings import CONFIG, LLMConfig
# ⚠️ 注意：不要在这里 import 旧 slicer/extractor。
# 你现在的主线是 ruleset + RuleEngineSlicer / RuleEngineExtractorRunner。
# 旧类如果保留，也应该在 _build_default_components() 内部按需惰性 import。

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
        self.benchmark_dir = (
            benchmark_dir or Path(__file__).resolve().parents[1] / "benchmarks"
        )
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

    def evaluate_runner(
        self,
        runner: Any,
        *,
        override: Optional[ExtractRuleSet] = None,
    ) -> List[dict]:
        if not self.benchmarks or runner is None:
            return []

        results: List[dict] = []

        for bench in self.benchmarks:
            slug = bench.get("extractor_slug")
            input_md = bench.get("input_md", "") or ""
            expected = bench.get("expected", []) or []
            report_type = bench.get("report_type")

            ctx = ReportContext()
            ctx.set_markdown(input_md)

            if report_type:
                ctx.set_metadata(report_type=report_type)

            outputs = runner.run(ctx, override=override) or {}
            actual = outputs.get(slug, []) or []
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
        extractor_runner: Optional[Any] = None,
        evaluator: Optional[BenchmarkEvaluator] = None,
        validators: Optional[Sequence[BaseValidator]] = None,
        llm_config: Optional[LLMConfig] = None,
        model_id: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        self.converter = converter or MarkdownFileConverter()
        self.type_detector = type_detector or ReportTypeDetector()
        self.evaluator = evaluator or BenchmarkEvaluator()
        self.validators = list(validators) if validators is not None else []

        cfg = llm_config or CONFIG

        self.model_id = model_id or cfg.model_id
        self.base_url = base_url or cfg.base_url
        self.api_key = api_key if api_key is not None else cfg.api_key

        self.default_debug = debug
        self.debug = debug

        self.slicers = list(slicers) if slicers is not None else []
        self.extractor_runner = extractor_runner

        if slicers is None and extractor_runner is None:
            self.slicers, self.extractor_runner = self._build_default_components()

    def _log(self, msg: str, debug) -> None:
        if debug:
            print(msg)

    def _build_default_components(self) -> tuple[list[Any], Optional[Any]]:
        try:
            slicers = [
                RuleEngineSlicer(debug=self.default_debug),
            ]

            extractor_runner = RuleEngineExtractorRunner(
                debug=self.default_debug,
                model_id=self.model_id,
                base_url=self.base_url,
                api_key=self.api_key,
            )
            return slicers, extractor_runner
        except Exception as e:
            if self.default_debug:
                print(f"⚠️ _build_default_components failed: {e!r}")
            return [], None

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

    def load_bytes(
        self,
        file_bytes: bytes,
        *,
        filename: Optional[str] = None,
        context: Optional[ReportContext] = None,
        debug: bool = False,
    ) -> ReportContext:
        """
        bytes -> markdown -> ReportContext
        用于 ExtractService / 节点：拿到文件 bytes 后直接交给 pipeline
        """
        if context is not None:
            return context

        if debug:
            print(
                f"🚀 [LOAD_BYTES] filename={filename or '-'} size={len(file_bytes) if file_bytes else 0}"
            )

        start_time = time.time()

        ctx = ReportContext(source_path=Path(filename).resolve() if filename else None)

        md_text = self.converter.convert(file_bytes or b"", filename=filename)
        self._log(f"📄 BYTES->MD done chars={len(md_text)}", debug)

        ctx.set_markdown(md_text or "")
        self._log(f"⏱ load_bytes cost={time.time() - start_time:.2f}s", debug)
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
        context.set_metadata(
            report_type=rt,
            report_type_debug=info,
            report_type_confidence=res.confidence,
        )

        if debug:
            mode = (info or {}).get("mode")
            reason = (info or {}).get("reason")
            if mode == "strong":
                print(
                    f"🧠 detect report_type={rt} mode=strong hit={info.get('strong_text')} reason={reason}"
                )
            else:
                print(
                    f"🧠 detect report_type={rt} mode={mode} scores={info.get('scores')} reason={reason} conf={res.confidence}"
                )
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
        self._log(
            f"✅ slice done total_slices={total_slices} cost={time.time() - start_time:.2f}s",
            debug,
        )
        return context

    def step_extract(
        self,
        context: ReportContext,
        *,
        debug: bool = False,
        override: Optional[ExtractRuleSet] = None,
    ) -> Dict[str, List[dict]]:
        if debug:
            print("🧠 [EXTRACT] start")

        start_time = time.time()

        if self.extractor_runner is None:
            self._log("⚠️ no extractor_runner configured, skip", debug)
            return {}

        outputs = self.extractor_runner.run(context, override=override) or {}
        self._log(f"✨ runner extracted outputs={list(outputs.keys())}", debug)
        self._log(f"⏱ extract cost={time.time() - start_time:.2f}s", debug)
        return outputs

    # -------------------------
    # Validate
    # -------------------------
    def validate(
        self, outputs: Dict[str, List[dict]], debug: bool = False
    ) -> List[str]:
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
    def step_benchmark(
        self,
        *,
        override: Optional[ExtractRuleSet] = None,
        debug: bool = False,
    ) -> List[dict]:
        if self.extractor_runner is None:
            self._log("⚠️ no extractor_runner configured, skip benchmark", debug)
            return []

        results = self.evaluator.evaluate_runner(
            self.extractor_runner, override=override
        )
        self._log(f"📏 benchmark done count={len(results)}", debug)
        return results

    # -------------------------
    # Run / Run until
    # -------------------------
    def run(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        want_benchmark: bool = False,
        debug: Optional[bool] = None,
        override: Optional[ExtractRuleSet] = None,
    ) -> PipelineResult:
        debug = self.default_debug if debug is None else debug

        if debug:
            print("\n" + "=" * 60)
            print("🏁 ReportPipeline run")
            print("=" * 60)

        t0 = time.time()

        ctx = self.load(docx_path=docx_path, markdown_text=markdown_text, debug=debug)
        self.step_detect_report_type(ctx, debug=debug)
        self.step_slice(ctx, debug=debug)
        outputs = self.step_extract(ctx, debug=debug, override=override)
        warnings = self.validate(outputs, debug=debug)

        evaluations: List[dict] = []
        if want_benchmark:
            evaluations = self.step_benchmark(override=override, debug=debug)

        if debug:
            print("-" * 60)
            print(
                f"🎉 done cost={time.time() - t0:.2f}s warnings={len(warnings)} eval={len(evaluations)}"
            )
            print("=" * 60 + "\n")

        return PipelineResult(
            context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings
        )

    def run_bytes(
        self,
        file_bytes: bytes,
        filename: Optional[str] = None,
        *,
        want_benchmark: bool = False,
        debug: Optional[bool] = None,
        override: Optional[ExtractRuleSet] = None,
    ) -> PipelineResult:
        debug = self.default_debug if debug is None else debug

        if debug:
            print("\n" + "=" * 60)
            print("🏁 ReportPipeline run_bytes")
            print("=" * 60)

        t0 = time.time()

        ctx = self.load_bytes(file_bytes, filename=filename, debug=debug)
        self.step_detect_report_type(ctx, debug=debug)
        self.step_slice(ctx, debug=debug)
        outputs = self.step_extract(ctx, debug=debug, override=override)
        warnings = self.validate(outputs, debug=debug)

        evaluations: List[dict] = []
        if want_benchmark:
            evaluations = self.step_benchmark()

        if debug:
            print("-" * 60)
            print(
                f"🎉 done cost={time.time() - t0:.2f}s warnings={len(warnings)} eval={len(evaluations)}"
            )
            print("=" * 60 + "\n")

        return PipelineResult(
            context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings
        )

    def run_until(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        until: RunStage = "all",
        want_benchmark: bool = False,
        debug: bool = False,
        override: Optional[ExtractRuleSet] = None,
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

        outputs = self.step_extract(ctx, debug=debug, override=override)
        if until == "extract":
            return ctx, outputs

        warnings = self.validate(outputs, debug=debug)
        if until == "validate":
            return ctx, outputs, warnings

        evaluations: List[dict] = []
        if want_benchmark or until in ("benchmark", "all"):
            evaluations = self.step_benchmark(override=override, debug=debug)

        return PipelineResult(
            context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings
        )

    def run_until_bytes(
        self,
        file_bytes: bytes,
        *,
        filename: Optional[str] = None,
        until: RunStage = "all",
        slice_only: bool = True,
        want_benchmark: bool = False,
        debug: bool = False,
    ):
        ctx = self.load_bytes(file_bytes, filename=filename, debug=debug)
        if until == "load":
            return ctx

        self.step_detect_report_type(ctx, debug=debug)
        if until == "detect":
            return ctx

        self.step_slice(ctx, debug=debug)
        if until == "slice":
            return ctx

        outputs = self.step_extract(ctx, debug=debug)
        if until == "extract":
            return ctx, outputs

        warnings = self.validate(outputs, debug=debug)
        if until == "validate":
            return ctx, outputs, warnings

        evaluations: List[dict] = []
        if want_benchmark or until in ("benchmark", "all"):
            evaluations = self.step_benchmark()

        return PipelineResult(
            context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings
        )
