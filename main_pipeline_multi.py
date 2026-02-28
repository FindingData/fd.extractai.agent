from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Callable

from app.report.pipeline import ReportPipeline, PipelineResult  # 你把方案A那份放到这里即可
from app.report.sections.LetterToClientRegexSlicer import LetterToClientRegexSlicer  # 你把切片器放到这里即可
from app.report.sections.valuation_tables import ValuationTablesSlicer  # 你把切片器放到这里即可
from app.report.extractors.valuation import ValuationExtractor  # 你把抽取器放到这里即可
# ============================================================
# 文件落盘工具
# ============================================================

def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s or "", encoding="utf-8")


def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _brief(s: str, n: int = 160) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s[:n] + ("..." if len(s) > n else "")


# ============================================================
# Persist：把一次 PipelineResult 落到 md/short/outputs 目录
# ============================================================

def make_file_persist(md_dir: Path, short_dir: Path, out_dir: Path) -> Callable[[str, PipelineResult], None]:
    md_dir.mkdir(parents=True, exist_ok=True)
    short_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    def persist(doc_id: str, result: PipelineResult) -> None:
        ctx = result.context
        outputs = result.outputs or {}

        # 1) md
        md_path = md_dir / f"{doc_id}.md"
        _write_text(md_path, ctx.markdown_text or "")

        # 2) short slices（给人看）
        doc_short = short_dir / doc_id
        doc_short.mkdir(parents=True, exist_ok=True)

        preview = {}
        slice_stats = {k: len(v) for k, v in (ctx.slices or {}).items()}
        for key, sections in (ctx.slices or {}).items():
            preview[key] = []
            for idx, sec in enumerate(sections, 1):
                out_path = doc_short / f"{key}__{idx}.md"
                _write_text(out_path, f"{sec.title}\n\n{sec.text}")
                preview[key].append(
                    {
                        "file": out_path.name,
                        "title": sec.title,
                        "meta": sec.metadata,
                        "preview": _brief(sec.text),
                    }
                )

        _write_json(doc_short / "slices.json", {"stats": slice_stats, "preview": preview})

        # 3) outputs
        doc_out = out_dir / doc_id
        doc_out.mkdir(parents=True, exist_ok=True)

        outputs_stats = {slug: len(rows or []) for slug, rows in outputs.items()}

        _write_json(doc_out / "outputs.json", outputs)
        _write_json(doc_out / "outputs_stats.json", outputs_stats)
        _write_json(doc_out / "slice_stats.json", slice_stats)

        # 4) warnings / evaluations（可选，但很建议落）
        if result.warnings:
            _write_json(doc_out / "warnings.json", result.warnings)
        if result.evaluations:
            _write_json(doc_out / "benchmarks.json", result.evaluations)

    return persist


# ============================================================
# Batch：一次遍历 docx，跑完整流程（convert->slice->extract->validate）
# ============================================================

def run_batch_docx(
    input_dir: Path,
    pipe: ReportPipeline,
    *,
    md_dir: Path,
    short_dir: Path,
    out_dir: Path,
    slice_only: bool = True,
    want_benchmark: bool = False,  # 批处理通常关掉，想跑单独跑 benchmark 命令
    debug: bool = False,
) -> Dict[str, Any]:
    persist = make_file_persist(md_dir, short_dir, out_dir)

    docx_files = sorted(input_dir.glob("*.docx"))
    summary: Dict[str, Any] = {
        "total": len(docx_files),
        "success": 0,
        "failed": 0,
        "items": [],
    }

    print(f"📂 输入: {input_dir}  docx={len(docx_files)}")
    print(f"🧾 输出: md={md_dir} short={short_dir} outputs={out_dir}")
    print("=" * 90)

    for i, docx in enumerate(docx_files, 1):
        doc_id = docx.stem
        print(f"▶ [{i}/{len(docx_files)}] {docx.name}")

        try:
            # ✅ 方案A调用方式：load()->slice()->extract() 或直接 run()
            # 我这里用 run()：内部会做 slice + extract + validate（warnings）
            result = pipe.run(
                docx_path=docx,
                slice_only=slice_only,
                want_benchmark=want_benchmark,
                debug=debug,
            )

            persist(doc_id, result)

            summary["success"] += 1
            summary["items"].append(
                {
                    "doc": doc_id,
                    "ok": True,
                    "warnings": len(result.warnings or []),
                }
            )

            if result.warnings:
                print(f"   ⚠️ warnings={len(result.warnings)}")

        except Exception as e:
            summary["failed"] += 1
            err = str(e)
            summary["items"].append({"doc": doc_id, "ok": False, "error": err})

            # 错误落盘
            doc_out = out_dir / doc_id
            doc_out.mkdir(parents=True, exist_ok=True)
            _write_text(doc_out / "error.traceback.txt", traceback.format_exc())

            print(f"   ❌ {err}")

    _write_json(out_dir / "batch_summary.json", summary)

    print("=" * 90)
    print(f"🏁 完成：✅ success={summary['success']}  ❌ failed={summary['failed']}")
    print(f"📦 汇总: {out_dir / 'batch_summary.json'}")
    return summary


# ============================================================
# 单文件调试：更“链式”的写法（需要看中间态就用这个）
# ============================================================

def debug_one_docx(docx_path: Path, pipe: ReportPipeline) -> None:
    doc_id = docx_path.stem
    run = pipe.load(docx_path=docx_path)     # ✅ 生成本次会话 ReportRun
    run.slice()                              # ✅ 切片
    outputs = run.extract(slice_only=True, debug=True)  # ✅ 抽取 + validate（warnings 挂在 run 上）
    dbg = run.debug_info(outputs)

    print(f"\n🧪 DEBUG {doc_id}")
    print("slice_stats =", dbg.slice_stats)
    print("outputs_stats =", dbg.outputs_stats)
    if run.warnings:
        print("warnings:")
        for w in run.warnings:
            print(" -", w)


# ============================================================
# main
# ============================================================

if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    app_root = current_file.parent  # 你自己确认路径

    input_dir = app_root / "inputs" / "report_detect"

    md_dir = input_dir / "_md"
    short_dir = input_dir / "_short"
    out_dir = input_dir / "_outputs"

    TABLE_PATTERNS = [
    r"估\s*价\s*对\s*象\s*基\s*本\s*情\s*况\s*一\s*览\s*表",
    r"估\s*价\s*结\s*果\s*一\s*览\s*表",
    r"估\s*价\s*结\s*果\s*汇\s*总\s*表",
    ]

    pipe = ReportPipeline(
        slicers=[
            # 1) 先切出致函
            LetterToClientRegexSlicer(
                start_pattern=r"致\s*估\s*价\s*委\s*托\s*人\s*函[：:]?",
                end_pattern=r"目\s*录",
                fallback_chars=600,
            ),
            # 2) 再用致函去定位“结果一览表/汇总表”，找不到则 fallback 到致函
            ValuationTablesSlicer(
                letter_key="letter_to_client",
                table_patterns=TABLE_PATTERNS,          # ✅ 外部传入
                search_after_letter_chars=12000,        # 致函后窗口
                max_table_chars=12000,
                fallback_letter_chars=6000,             # ✅ 找不到表 -> 回退到致函
                allow_fulltext_search_if_no_anchor=False
            ),
        ],
        extractors=[
            ValuationExtractor(),
        ],
    )

    # 1) 批处理（一次遍历 docx，就产出 md/short/outputs）
    run_batch_docx(
        input_dir=input_dir,
        pipe=pipe,
        md_dir=md_dir,
        short_dir=short_dir,
        out_dir=out_dir,
        slice_only=True,
        want_benchmark=False,
        debug=True,
    )

    # 2) 单文件调试（你需要看切片命中/每个 extractor 输入时用）
    # debug_one_docx(input_dir / "xxx.docx", pipe)