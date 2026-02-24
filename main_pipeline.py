from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.report.context import ReportContext, ReportSection
from app.report.sections.letter_to_client import LetterToClientSlicer
from app.report.sections.valuation_tables import ValuationTablesSlicer

from app.report.extractors.valuation import ValuationExtractor
from app.report.extractors.purpose import PurposeExtractor
from app.report.extractors.assumptions import AssumptionsExtractor
from app.report.extractors.method import MethodExtractor
from app.report.extractors.conclusion import ConclusionExtractor

# 你项目里已有：docx->md 的工具
from app.utils.text_utils import convert_docx_to_md

from app.report.pipeline import ReportPipeline

def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s or "", encoding="utf-8")


def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _brief(s: str, n: int = 140) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s[:n] + ("..." if len(s) > n else "")


def batch_convert_docx_to_md(input_dir: Path, md_dir: Path, pipe: ReportPipeline) -> List[Path]:
    md_dir.mkdir(parents=True, exist_ok=True)
    docx_files = sorted(input_dir.glob("*.docx"))

    print(f"📂 阶段1/3：DOCX -> MD")
    print(f"   输入: {input_dir}  文件数={len(docx_files)}")
    print(f"   输出: {md_dir}")

    md_paths: List[Path] = []
    for i, docx in enumerate(docx_files, 1):
        try:
            print(f"⏳ [{i}/{len(docx_files)}] 转换 {docx.name} ...", end="", flush=True)

            ctx = pipe.step_convert(docx_path=docx)   # ✅ 用 pipeline
            md = ctx.markdown_text or ""

            md_path = md_dir / f"{docx.stem}.md"
            _write_text(md_path, md)
            md_paths.append(md_path)

            print(" ✅")
        except Exception as e:
            print(f" ❌ {e}")

    print(f"✨ 转换完成：成功 {len(md_paths)} 个\n")
    return md_paths


# ---------------------------
# Step 2) Slice (定位切片 + 落盘)
# ---------------------------
def slice_markdown_files(
    md_paths: Sequence[Path],
    short_dir: Path,
    pipe: ReportPipeline,
) -> Dict[str, Dict[str, Any]]:
    short_dir.mkdir(parents=True, exist_ok=True)

    print(f"✂️ 阶段2/3：定位切片")
    print(f"   输入MD数: {len(md_paths)}")
    print(f"   输出short: {short_dir}\n")

    stats: Dict[str, Dict[str, Any]] = {}

    for i, md_path in enumerate(md_paths, 1):
        print(f"🧭 [{i}/{len(md_paths)}] 切片 {md_path.name}")

        md_text = md_path.read_text(encoding="utf-8")

        # ✅ 用 pipeline: convert 已经做过了，这里直接 step_convert(markdown_text=...)
        ctx = pipe.step_convert(markdown_text=md_text)
        pipe.step_slice(ctx)  # ✅ 关键：让 slicers 填充 ctx.slices

        doc_out = short_dir / md_path.stem
        doc_out.mkdir(parents=True, exist_ok=True)

        slice_stats = {}
        preview = {}

        for key, sections in (ctx.slices or {}).items():
            slice_stats[key] = len(sections)
            preview[key] = []

            for idx2, sec in enumerate(sections):
                out_path = doc_out / f"{key}__{idx2+1}.md"
                _write_text(out_path, f"{sec.title}\n\n{sec.text}")

                preview[key].append(
                    {
                        "file": out_path.name,
                        "title": sec.title,
                        "meta": sec.metadata,
                        "preview": _brief(sec.text),
                    }
                )

        print("   ✅ 命中统计:", slice_stats)
        _write_json(doc_out / "slices.json", {"stats": slice_stats, "preview": preview})

        stats[md_path.stem] = {"slice_stats": slice_stats}

    print("\n✨ 切片完成\n")
    return stats


# ---------------------------
# Step 3) Extract (只喂 short 文本到 LangExtract)
# ---------------------------
def extract_from_md(
    md_dir: Path,
    out_dir: Path,
    pipe: ReportPipeline,
    *,
    slice_only: bool = True,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(md_dir.glob("*.md"))
    print(f"🤖 阶段3/3：LangExtract 抽取（先切片再抽）")
    print(f"   输入md: {md_dir}  文件数={len(md_files)}")
    print(f"   输出结果: {out_dir}\n")

    summary = {"total": len(md_files), "success": 0, "failed": 0, "items": []}

    for i, md_path in enumerate(md_files, 1):
        doc_stem = md_path.stem
        print("=" * 90)
        print(f"▶ [{i}/{len(md_files)}] 抽取: {doc_stem}")

        doc_out = out_dir / doc_stem
        doc_out.mkdir(parents=True, exist_ok=True)

        ok = True
        errors: List[str] = []

        try:
            md_text = md_path.read_text(encoding="utf-8")

            ctx = pipe.step_convert(markdown_text=md_text)
            pipe.step_slice(ctx)

            outputs = pipe.step_extract(ctx, slice_only=slice_only)  # ✅ 关键
            _write_json(doc_out / "outputs.json", outputs)

            outputs_stats = {slug: len(rows or []) for slug, rows in outputs.items()}
            _write_json(doc_out / "outputs_stats.json", outputs_stats)

            slice_stats = {k: len(v) for k, v in (ctx.slices or {}).items()}
            _write_json(doc_out / "slice_stats.json", slice_stats)

            print("   ✂️ slice_stats:", slice_stats)
            print("   ✅ outputs_stats:", outputs_stats)

            summary["success"] += 1

        except Exception as e:
            ok = False
            err = str(e)
            errors.append(err)
            tb = traceback.format_exc()
            _write_text(doc_out / "error.traceback.txt", tb)
            print("   ❌ error:", err)
            summary["failed"] += 1

        summary["items"].append({"doc": doc_stem, "ok": ok, "errors": errors})

    _write_json(out_dir / "batch_summary.json", summary)
    print("\n🏁 抽取完成")
    print(f"✅ success={summary['success']}  ❌ failed={summary['failed']}")
    print(f"📦 汇总: {out_dir / 'batch_summary.json'}")
    return summary


if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    app_root = current_file.parent  # 你自己确认路径
    input_dir = app_root / "inputs" / "report_hf"

    md_dir = input_dir / "_md"
    short_dir = input_dir / "_short"
    out_dir = input_dir / "_outputs"

    pipe = ReportPipeline()

    # 1) docx -> md
    md_paths = batch_convert_docx_to_md(input_dir, md_dir, pipe)

    # 2) md -> short slices（落盘给人看）
    slice_markdown_files(md_paths, short_dir, pipe)

    # 3) md -> slice -> extract（逻辑上仍是先定位切片再抽）
    extract_from_md(md_dir, out_dir, pipe, slice_only=True)