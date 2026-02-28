from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple,Literal

from app.report.context import ReportContext, ReportSection
from app.report.sections.letter_to_client import LetterToClientSlicer
from app.report.sections.valuation_tables import ValuationTablesSlicer

from app.report.extractors.valuation import ValuationExtractor
from app.report.extractors.purpose import PurposeExtractor
from app.report.extractors.assumptions import AssumptionsExtractor
from app.report.extractors.method import MethodExtractor
from app.report.extractors.conclusion import ConclusionExtractor
from app.utils.report_utils import ReportType, detect_report_type_from_md_head
from app.utils.text_utils import convert_docx_to_md,convert_word_to_md
from app.report.rules.ReportProfileRegistry import ReportProfile, ReportProfileRegistry


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


@dataclass
class StepDebug:
    slice_stats: Dict[str, int]
    outputs_stats: Dict[str, int]


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
        registry = {extractor.slug: extractor for extractor in extractors}
        results: List[dict] = []

        for bench in self.benchmarks:
            slug = bench.get("extractor_slug")
            extractor = registry.get(slug)
            if not extractor:
                continue

            ctx = ReportContext()
            ctx.set_markdown(bench["input_md"])

            # benchmark：直接塞 slice，避免 slicer 干扰
            if getattr(extractor, "target_slice_key", "__full__") != "__full__":
                ctx.add_slice(
                    ReportSection(
                        key=extractor.target_slice_key,
                        title=f"{bench['name']}#{slug}",
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
# Validators (可选：抽取后校验，返回 warnings)
# ============================================================

class BaseValidator:
    def __call__(self, outputs: Dict[str, List[dict]]) -> List[str]:
        return []

# ============================================================
# Pipeline (按你要的结构：load/step_slice/step_extract/step_benchmark)
# ============================================================
import time
class ReportPipeline:
        
    def _default_profiles(self) -> ReportProfileRegistry:
        """
        适配你的 ReportType = Literal["house", "land", "asset"]
        - default_profile 兜底使用 house（也可以换成你认为最通用的一套）
        - 三类都可以复用大部分 slicers/extractors，但 rules/prompt_pack 可分别配置
        """
        house = ReportProfile(
            report_type="house",
            slicers=[
                LetterToClientSlicer(),
                ValuationTablesSlicer(),
                # 你后续如果要加 house 特有 slicer，就加在这里
            ],
            extractors=[
                ValuationExtractor(),
                PurposeExtractor(),
                AssumptionsExtractor(),
                MethodExtractor(),
                ConclusionExtractor(),
            ],
            rules={"prompt_pack": "house_v1"},
        )

        land = ReportProfile(
            report_type="land",
            slicers=[
                LetterToClientSlicer(),
                ValuationTablesSlicer(),
                # 例如：LandTablesSlicer() / LandRightsSlicer() 等
            ],
            extractors=[
                ValuationExtractor(),
                PurposeExtractor(),
                AssumptionsExtractor(),
                MethodExtractor(),
                ConclusionExtractor(),
                # 例如：LandUseExtractor() / PlanningIndexExtractor() 等
            ],
            rules={"prompt_pack": "land_v1"},
        )

        asset = ReportProfile(
            report_type="asset",
            slicers=[
                LetterToClientSlicer(),
                ValuationTablesSlicer(),
                # 例如：AssetScopeSlicer() / AssetListSlicer() 等
            ],
            extractors=[
                ValuationExtractor(),
                PurposeExtractor(),
                AssumptionsExtractor(),
                MethodExtractor(),
                ConclusionExtractor(),
                # 例如：AssetScopeExtractor() / AssetApproachExtractor() 等
            ],
            rules={"prompt_pack": "asset_v1"},
        )

        return ReportProfileRegistry(
            profiles={
                "house": house,
                "land": land,
                "asset": asset,
            },
            default_profile=house,  # 兜底
        )

    def __init__(
        self,
        *,
        converter: Optional[MarkdownFileConverter] = None,
        profile_registry: ReportProfileRegistry | None = None,
        slicers: Optional[Sequence] = None,
        extractors: Optional[Sequence] = None,
        evaluator: Optional[BenchmarkEvaluator] = None,
        validators: Optional[Sequence[BaseValidator]] = None,
    ) -> None:
        self.converter = converter or MarkdownFileConverter()
        self.profile_registry = profile_registry or self._default_profiles()
        self.slicers = list(slicers) if slicers is not None else [
            LetterToClientSlicer(),
            ValuationTablesSlicer(),
        ]
        self.extractors = list(extractors) if extractors is not None else [
            ValuationExtractor(),
            PurposeExtractor(),
            AssumptionsExtractor(),
            MethodExtractor(),
            ConclusionExtractor(),
        ]
        self.evaluator = evaluator or BenchmarkEvaluator()
        self.validators = list(validators) if validators is not None else []

    def _log(self, msg: str, debug: bool = True):
        """统一的内部日志格式"""
        if debug:
            print(f"  {msg}")

    def _get_profile(self, ctx: ReportContext) -> ReportProfile:
        rt = (ctx.metadata or {}).get("report_type") or "house"
        return self.profile_registry.get(rt)
    # -------------------------
    # Load
    # -------------------------
    def load(
        self,
        *,
        docx_path: Optional[str | Path] = None,
        markdown_text: Optional[str] = None,
        context: Optional[ReportContext] = None,
        debug: bool = False
    ) -> ReportContext:
        if debug:
            source = docx_path or "Markdown Text"
            print(f"🚀 [1/4] 加载报告资源: {source}")
        
        start_time = time.time()
        if context is not None:
            return context

        path_obj = Path(docx_path) if docx_path else None
        ctx = ReportContext(source_path=path_obj)

        if docx_path:
            md_text = self.converter.convert(path_obj)
            self._log(f"📄 已完成 DOCX 转 Markdown ({len(md_text)} 字符)", debug)
        else:
            md_text = markdown_text or ""

        ctx.set_markdown(md_text)
        self._log(f"⏱  加载耗时: {time.time() - start_time:.2f}s", debug)
        return ctx
    
    # -------------------------
    # tetect
    # -------------------------
    def step_detect_report_type(
        self,
        context: ReportContext,
        *,
        head_chars: int = 2000,
        debug: bool = False,
    ) -> str:
        """
        从 markdown 开头识别报告类型，写入 context.metadata["report_type"]。
        """
        md = context.ensure_markdown()

        rt, info = detect_report_type_from_md_head(md, head_chars=head_chars)
        context.set_metadata(report_type=rt, report_type_debug=info)
        if debug:
            mode = info.get("mode")
            if mode == "strong":
                print(f"🧠 报告类型识别: report_type={rt} mode=strong hit={info.get('strong_text')} reason={info.get('reason')}")
            else:
                print(f"🧠 报告类型识别: report_type={rt} scores={info.get('scores')} reason={info.get('reason')}")
        return rt
    
    
    def _prepare_extractor_inputs(
        self,
        context: ReportContext,
        *,
        slice_only: bool,
        empty_if_missing_slice: bool,
        debug: bool,
        max_slice_chars: int,
    ) -> Dict[str, Optional[ReportContext]]:
        """
        为每个 Extractor 选择输入：
        - slice_only=True：优先使用 extractor 指定切片；若 extractor 要 __full__ 则用全文
        - slice_only=False：全部用全文
        """
        inputs: Dict[str, Optional[ReportContext]] = {}

        for extractor in self.extractors:
            slug = extractor.slug
            target_key = getattr(extractor, "target_slice_key", "__full__")

            # 1) 非切片模式：全部看全文
            if not slice_only:
                inputs[slug] = context
                continue

            # 2) 切片模式：__full__ 也允许跑（否则 assumptions/method/conclusion 会被跳过）
            if target_key == "__full__":
                inputs[slug] = context
                continue

            # 3) 切片模式：找对应切片
            slices = context.get_slices(target_key)
            if not slices:
                if debug:
                    self._log(f"🔍 [INPUT] {slug}: 未找到切片 {target_key}", debug)
                inputs[slug] = None if empty_if_missing_slice else context
                continue

            slice_text = "\n\n".join(s.text for s in slices if s and s.text).strip()
            if not slice_text:
                inputs[slug] = None
                continue

            if max_slice_chars and len(slice_text) > max_slice_chars:
                slice_text = slice_text[:max_slice_chars]

            # ✅ 给 extractor 一个“专注切片”的临时 context
            tmp_ctx = ReportContext(source_path=context.source_path)
            tmp_ctx.set_markdown(slice_text)

            # ✅ 关键：复制 metadata（让 report_type-aware examples 生效）
            if context.metadata:
                tmp_ctx.set_metadata(**context.metadata)

            for s in slices:
                tmp_ctx.add_slice(s)

            inputs[slug] = tmp_ctx

        return inputs
    # -------------------------
    # Slice
    # -------------------------
    def step_slice(self, context: ReportContext, debug: bool = False) -> ReportContext:
        if debug:
            print(f"✂️  [2/4] 执行文本分段 (Slicing)...")
        
        start_time = time.time()
        context.ensure_markdown()
        for slicer in self.slicers:
            slicer_name = slicer.__class__.__name__
            slicer(context)
            # 获取该 slicer 刚刚产生的 slice 数量 (仅示意)
            self._log(f"🔹 执行 {slicer_name}", debug)
        
        total_slices = sum(len(v) for v in (context.slices or {}).values())
        self._log(f"✅ 分段完成！共定位到 {total_slices} 个核心章节 (耗时: {time.time() - start_time:.2f}s)", debug)
        return context

    # -------------------------
    # Extract
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
            mode = "切片模式" if slice_only else "全文模式"
            print(f"🧠 [3/4] 启动 LLM 智能抽取 (模式: {mode})")
        
        start_time = time.time()
        # A) 准备输入
        inputs = self._prepare_extractor_inputs(
            context,
            slice_only=slice_only,
            empty_if_missing_slice=empty_if_missing_slice,
            debug=debug,
            max_slice_chars=max_slice_chars,
        )

        # B) 执行抽取
        outputs: Dict[str, List[dict]] = {}
        registry = {ex.slug: ex for ex in self.extractors}

        for slug, in_ctx in inputs.items():
            ex_start = time.time()
            if in_ctx is None:
                outputs[slug] = []
                self._log(f"⚠️  [跳过] {slug.ljust(15)}: 未找到匹配章节", debug)
                continue
            
            results = registry[slug](in_ctx) or []
            outputs[slug] = results
            self._log(f"✨ [抽取] {slug.ljust(15)}: 发现 {len(results)} 条数据 (耗时: {time.time() - ex_start:.2f}s)", debug)

        self._log(f"⏱  抽取阶段总耗时: {time.time() - start_time:.2f}s", debug)
        return outputs

    # -------------------------
    # Validate
    # -------------------------
    def validate(self, outputs: Dict[str, List[dict]], debug: bool = False) -> List[str]:
        if debug:
            print(f"⚖️  [4/4] 执行房地产业务逻辑校验...")
        
        warnings: List[str] = []
        for v in self.validators:
            v_name = v.__class__.__name__
            try:
                current_warnings = v(outputs) or []
                if debug and current_warnings:
                    self._log(f"❗ {v_name} 检出 {len(current_warnings)} 个潜在问题", debug)
                warnings.extend(current_warnings)
            except Exception as e:
                warnings.append(f"⚠️ 校验器异常：{v_name}: {e}")
        
        if debug and not warnings:
            self._log("🟢 逻辑自洽性通过，未发现异常", debug)
        return warnings

    # -------------------------
    # 一键运行
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
            print("\n" + "="*60)
            print(f"🏁 开始处理房地产估价报告流水线")
            print("="*60)

        main_start = time.time()
        
        # 1. Load
        ctx = self.load(docx_path=docx_path, markdown_text=markdown_text, debug=debug)
        
        # 1.5 Detect report type  ✅ 新增
        self.step_detect_report_type(ctx, debug=debug)

        # 2. Slice
        self.step_slice(ctx, debug=debug)
        
        # 3. Extract
        outputs = self.step_extract(ctx, slice_only=slice_only, debug=debug)
        
        # 4. Validate
        warnings = self.validate(outputs, debug=debug)
        
        # 5. Benchmark (可选)
        evaluations = []
        if want_benchmark:
            if debug: print(f"📊 执行基准测试对比...")
            evaluations = self.step_benchmark()

        if debug:
            print("-" * 60)
            print(f"🎉 处理完成！总耗时: {time.time() - main_start:.2f}s")
            if warnings:
                print(f"🚩 风险提示: {len(warnings)} 条内容需人工复核")
            print("=" * 60 + "\n")

        return PipelineResult(context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings)
    
 

    RunStage = Literal["load", "detect", "slice", "extract", "validate", "benchmark", "all"]

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
        """
        只跑到指定阶段：
        - load: 只转换 markdown
        - detect: load + detect
        - slice: load + detect + slice
        - extract: ... + extract
        - validate: ... + validate
        - benchmark/all: ... (+ benchmark 可选)
        返回：根据阶段不同，返回 (ctx) / (ctx, outputs) / PipelineResult
        """
        # 1) load
        ctx = self.load(docx_path=docx_path, markdown_text=markdown_text, debug=debug)
        if until == "load":
            return ctx

        # 2) detect
        self.step_detect_report_type(ctx, debug=debug)
        if until == "detect":
            return ctx

        # 3) slice
        self.step_slice(ctx, debug=debug)
        if until == "slice":
            return ctx

        # 4) extract
        outputs = self.step_extract(ctx, slice_only=slice_only, debug=debug)
        if until == "extract":
            return ctx, outputs

        # 5) validate
        warnings = self.validate(outputs, debug=debug)
        if until == "validate":
            return ctx, outputs, warnings

        # 6) benchmark (可选)
        evaluations = []
        if want_benchmark or until in ("benchmark", "all"):
            evaluations = self.step_benchmark()

        return PipelineResult(context=ctx, outputs=outputs, evaluations=evaluations, warnings=warnings)