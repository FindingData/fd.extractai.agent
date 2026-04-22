from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages/fd-extractai-report/src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fd_extractai_report.analysis import ChecklistAnalyzer
from fd_extractai_report.pipeline import ReportPipeline
from fd_extractai_report.settings import LLMConfig


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[\\/:*?\"<>|]+", "_", value or "").strip()
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized.strip("._") or "unknown"


def _collect_sections(context: Any) -> List[Any]:
    sections: List[Any] = []
    for items in (getattr(context, "slices", None) or {}).values():
        sections.extend(items or [])
    return sections


def _serialize_sections(context: Any) -> List[Dict[str, Any]]:
    return [
        {
            "key": getattr(section, "key", None),
            "title": getattr(section, "title", None),
            "text": getattr(section, "text", ""),
            "len": len(getattr(section, "text", "") or ""),
            "metadata": getattr(section, "metadata", None) or {},
        }
        for section in _collect_sections(context)
    ]


def _build_llm_config() -> LLMConfig:
    return LLMConfig.from_env()


def _run_until_with_forced_type(
    pipe: ReportPipeline,
    *,
    file_path: Path,
    force_report_type: str | None,
    until: str,
) -> Any:
    context = pipe.load(docx_path=file_path, debug=True)
    if force_report_type:
        context.set_metadata(report_type=force_report_type)
        print(f"force_report_type={force_report_type}")
    else:
        pipe.step_detect_report_type(context, debug=True)

    if until == "slice":
        pipe.step_slice(context, debug=True)
        return context

    if until == "extract":
        pipe.step_slice(context, debug=True)
        outputs = pipe.step_extract(context, debug=True)
        return context, outputs

    raise ValueError(f"unsupported until: {until}")


def run_checklist_batch(
    *,
    input_dir: Path,
    out_dir: Path,
    force_report_type: str | None = "checklist",
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        list(input_dir.glob("*.doc")) + list(input_dir.glob("*.docx")),
        key=lambda path: path.name.lower(),
    )

    llm_config = _build_llm_config()
    pipe = ReportPipeline(debug=True, llm_config=llm_config)
    analyzer = ChecklistAnalyzer(llm_config=llm_config)

    print(f"input_dir={input_dir}")
    print(f"out_dir={out_dir}")
    print(f"files={len(files)}")

    batch_items: List[Dict[str, Any]] = []
    all_items: List[Dict[str, Any]] = []
    started_at = time.time()

    for index, file_path in enumerate(files, 1):
        print("\n" + "=" * 80)
        print(f"[{index}/{len(files)}] {file_path.name}")
        print("=" * 80)

        file_dir = out_dir / _safe_name(file_path.stem)
        file_dir.mkdir(parents=True, exist_ok=True)

        try:
            slice_ctx = _run_until_with_forced_type(
                pipe,
                file_path=file_path,
                force_report_type=force_report_type,
                until="slice",
            )
            extract_ctx, outputs = _run_until_with_forced_type(
                pipe,
                file_path=file_path,
                force_report_type=force_report_type,
                until="extract",
            )

            markdown_text = extract_ctx.ensure_markdown()
            report_type = (extract_ctx.metadata or {}).get("report_type")
            items = outputs.get("items", []) or []
            analyzed = analyzer.analyze(items)
            analysis_md = analyzer.to_markdown(
                analyzed,
                title=f"{file_path.stem} 资料清单汇总（去重分类）",
            )

            markdown_path = file_dir / f"{file_path.stem}.md"
            markdown_path.write_text(markdown_text, encoding="utf-8")

            _write_json(
                file_dir / f"{file_path.stem}.sections.json",
                {
                    "file": file_path.name,
                    "path": str(file_path),
                    "report_type": report_type,
                    "slice_keys": slice_ctx.slice_keys(),
                    "slice_counts": slice_ctx.slice_counts(),
                    "sections": _serialize_sections(slice_ctx),
                },
            )
            _write_json(file_dir / f"{file_path.stem}.extract.json", outputs)
            _write_json(file_dir / f"{file_path.stem}.analysis.json", analyzed)
            (file_dir / f"{file_path.stem}.analysis.md").write_text(
                analysis_md,
                encoding="utf-8",
            )

            batch_items.append(
                {
                    "file": file_path.name,
                    "path": str(file_path),
                    "report_type": report_type,
                    "slice_keys": slice_ctx.slice_keys(),
                    "slice_counts": slice_ctx.slice_counts(),
                    "items_count": len(items),
                    "analysis_count": len(analyzed),
                    "output_dir": str(file_dir),
                    "ok": True,
                }
            )

            all_items.extend(items)
            print(
                f"report_type={report_type} items={len(items)} analyzed={len(analyzed)}"
            )
        except Exception as exc:
            batch_items.append(
                {
                    "file": file_path.name,
                    "path": str(file_path),
                    "error": repr(exc),
                    "output_dir": str(file_dir),
                    "ok": False,
                }
            )
            print(f"failed: {exc!r}")

    merged_analysis = analyzer.analyze(all_items)
    merged_markdown = analyzer.to_markdown(merged_analysis, title="资料清单总汇（去重分类）")

    summary = {
        "input_dir": str(input_dir),
        "out_dir": str(out_dir),
        "force_report_type": force_report_type,
        "patterns": ["*.doc", "*.docx"],
        "total": len(files),
        "success": sum(1 for item in batch_items if item.get("ok")),
        "failed": sum(1 for item in batch_items if not item.get("ok")),
        "raw_items_count": len(all_items),
        "merged_analysis_count": len(merged_analysis),
        "elapsed_ms": int((time.time() - started_at) * 1000),
        "items": batch_items,
    }

    _write_json(out_dir / "checklist.batch.json", summary)
    _write_json(out_dir / "checklist.items.json", all_items)
    _write_json(out_dir / "checklist.analysis.json", merged_analysis)
    (out_dir / "checklist.analysis.md").write_text(merged_markdown, encoding="utf-8")

    print("\n" + "-" * 80)
    print(
        f"done total={summary['total']} success={summary['success']} failed={summary['failed']}"
    )
    print(f"raw_items={summary['raw_items_count']} merged={summary['merged_analysis_count']}")
    print(f"summary={out_dir / 'checklist.batch.json'}")

    return summary


def main() -> None:
    input_dir = ROOT / "inputs" / "zlqd"
    out_dir =  input_dir / "_outputs" / "checklist_pipeline"

    result = run_checklist_batch(
        input_dir=input_dir,
        out_dir=out_dir,
        force_report_type="checklist",
    )
    assert result["total"] > 0, "未找到可处理的 doc/docx 文件"
    assert result["success"] > 0, "批处理未成功生成任何结果"


if __name__ == "__main__":
    main()
