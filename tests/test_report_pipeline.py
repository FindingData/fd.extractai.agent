from __future__ import annotations

import sys
import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import CONFIG
from fd_extractai_report.pipeline import ReportPipeline


# -----------------------------
# helpers
# -----------------------------


def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_key(key: str) -> str:
    key = key or "unknown"
    return re.sub(r"[^0-9a-zA-Z_\-\.]+", "_", key).strip("_") or "unknown"


def _preview(s: str, n: int = 160) -> str:
    s = (s or "").replace("\n", "\\n")
    return s[:n] + ("..." if len(s) > n else "")


def dump_sections(sections, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for sec in sorted(sections, key=lambda s: (getattr(s, "key", "") or "")):
        key = _safe_key(getattr(sec, "key", "") or "unknown")
        text = (getattr(sec, "text", None) or "").strip("\n")

        p = out_dir / f"{stem}.{key}.md"
        p.write_text(text, encoding="utf-8")

        print(f"📝 wrote slice: {p.name} len={len(text)}")


def _price_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"ok": False}

    row = rows[0]

    return {
        "total_price": row.get("total_price"),
        "unit_price": row.get("unit_price"),
        "items": len(row.get("items") or [])
        if isinstance(row.get("items"), list)
        else None,
        "confidence": row.get("confidence"),
    }


# -----------------------------
# batch runner
# -----------------------------


def run_extract_batch(
    *,
    input_dir: Path,
    out_dir: Path,
    pipe: ReportPipeline,
    patterns: Optional[List[str]] = None,
    use_bytes: bool = False,
) -> Dict[str, Any]:

    out_dir.mkdir(parents=True, exist_ok=True)

    patterns = patterns or ["*.doc", "*.docx"]

    files: List[Path] = []

    for pat in patterns:
        files.extend(input_dir.glob(pat))

    files = sorted(
        {p.resolve(): p for p in files}.values(),
        key=lambda p: p.name.lower(),
    )

    print(f"📂 Extract 批测试：{input_dir}")
    print(f"📦 输出: {out_dir}")
    print(f"files={len(files)}")

    items = []

    t0 = time.time()

    for i, f in enumerate(files, 1):

        print("\n" + "-" * 70)
        print(f"▶ [{i}/{len(files)}] {f.name}")

        try:

            # -----------------------------
            # pipeline run
            # -----------------------------

            if use_bytes:

                res = pipe.run_bytes(
                    f.read_bytes(),
                    filename=f.name,
                )

            else:

                res = pipe.run(
                    docx_path=f,
                )

            ctx = res.context
            outputs = res.outputs

            md = ctx.ensure_markdown() or ""

            report_type = (ctx.metadata or {}).get("report_type")

            print(f"🧠 report_type={report_type}")

            sections = []

            for v in (ctx.slices or {}).values():
                sections.extend(v)

            print(f"🧩 sections={len(sections)}")

            for j, s in enumerate(sections[:6], 1):

                text = getattr(s, "text", "") or ""

                print(
                    f"  - [{j}] key={getattr(s,'key',None)} "
                    f"title={getattr(s,'title',None)} "
                    f"len={len(text)} "
                    f"preview={_preview(text,120)}"
                )

            # -----------------------------
            # output dir
            # -----------------------------

            file_out_dir = out_dir / f.stem
            file_out_dir.mkdir(parents=True, exist_ok=True)

            # -----------------------------
            # markdown dump
            # -----------------------------

            md_out = file_out_dir / f"{f.stem}.md"
            md_out.write_text(md, encoding="utf-8")

            print(f"📝 wrote markdown {md_out.name}")

            # -----------------------------
            # slices dump
            # -----------------------------

            slices_dir = file_out_dir / "_slices"
            dump_sections(sections, slices_dir, f.stem)

            # -----------------------------
            # extract result
            # -----------------------------

            res_out = file_out_dir / f"{f.stem}.extract.json"

            _write_json(res_out, outputs)

            print(f"✅ wrote extract {res_out.name}")

            # -----------------------------
            # extractor outputs
            # -----------------------------

            extract_dir = file_out_dir / "_extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            extract_files = {}

            for slug, rows in (outputs or {}).items():

                safe_slug = _safe_key(slug)

                out_file = extract_dir / f"{safe_slug}.json"

                _write_json(out_file, rows)

                extract_files[slug] = str(out_file)

                print(f"📦 extractor {slug} rows={len(rows)}")

                if slug in ("price", "pricing"):

                    print("💰 price summary:")

                    print(
                        json.dumps(
                            _price_summary(rows),
                            ensure_ascii=False,
                            indent=2,
                        )
                    )

            # -----------------------------
            # sections json
            # -----------------------------

            sec_out = file_out_dir / f"{f.stem}.sections.json"

            sec_payload = {
                "file": f.name,
                "path": str(f),
                "report_type": report_type,
                "sections": [
                    {
                        "key": getattr(s, "key", None),
                        "title": getattr(s, "title", None),
                        "len": len(getattr(s, "text", "") or ""),
                        "metadata": getattr(s, "metadata", None) or {},
                    }
                    for s in sections
                ],
            }

            _write_json(sec_out, sec_payload)

            items.append(
                {
                    "file": f.name,
                    "path": str(f),
                    "report_type": report_type,
                    "sections": len(sections),
                    "extract_out": str(res_out),
                    "extractors": extract_files,
                    "ok": True,
                }
            )

        except Exception as e:

            print(f"❌ extract failed: {e}")

            items.append(
                {
                    "file": f.name,
                    "path": str(f),
                    "error": str(e),
                    "ok": False,
                }
            )

    result = {
        "input_dir": str(input_dir),
        "patterns": patterns,
        "total": len(files),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "items": items,
    }

    _write_json(out_dir / "extract.batch.json", result)

    print("\n" + "=" * 70)
    print(f"🏁 extract 完成 total={result['total']}")
    print(f"📦 summary {out_dir / 'extract.batch.json'}")

    return result


# -----------------------------
# main
# -----------------------------


if __name__ == "__main__":

    current_file = Path(__file__).resolve()

    app_root = current_file.parents[1]

    input_dir = app_root / "inputs" / "report_extract"

    out_dir = input_dir / "_outputs"

    pipe = ReportPipeline(
        model_id=CONFIG.QWEN_MODEL_NAME,
        base_url=CONFIG.QWEN_MODEL_URL,
        api_key=CONFIG.QWEN_KEY,
    )

    print("\n===== BYTES MODE =====")

    run_extract_batch(
        input_dir=input_dir,
        out_dir=out_dir / "bytes",
        pipe=pipe,
        patterns=["*.doc", "*.docx"],
        use_bytes=True,
    )