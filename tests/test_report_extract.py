from __future__ import annotations

import sys
import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fd_extractai_report import ReportPipeline

from fd_extractai_report.pipeline import ReportPipeline
from fd_extractai_report.settings import LLMConfig

# ✅ slicer + slicing rulesets（按你项目实际路径）
from fd_extractai_report.sections.rule_engine_slicer import RuleEngineSlicer
from fd_extractai_report.rules.slicing.default_rulesets import (
    ruleset_house as slice_ruleset_house,
    ruleset_land as slice_ruleset_land,
    ruleset_asset as slice_ruleset_asset,
)

# ✅ extractor runner（按你项目实际路径）
from fd_extractai_report.extractors.rule_engine_extractor import (
    RuleEngineExtractorRunner,
)


# -----------------------------
# helpers
# -----------------------------
def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_key(key: str) -> str:
    key = key or "unknown"
    return re.sub(r"[^0-9a-zA-Z_\-\.]+", "_", key).strip("_") or "unknown"


def _pick_slice_ruleset(report_type: str):
    rt = (report_type or "").lower()
    if "house" in rt:
        return slice_ruleset_house
    if "land" in rt:
        return slice_ruleset_land
    if "asset" in rt:
        return slice_ruleset_asset
    return slice_ruleset_house


def _preview(s: str, n: int = 160) -> str:
    s = (s or "").replace("\n", "\\n")
    return s[:n] + ("..." if len(s) > n else "")


def _sum_slice_chars(ctx, keys: List[str]) -> Tuple[int, Dict[str, Any]]:
    """
    统计用于抽取的 slice keys 命中情况：每个 key 有多少段、多少字符
    """
    stats: Dict[str, Any] = {}
    total = 0
    for k in keys:
        ss = ctx.get_slices(k) or []
        chars = sum(len((s.text or "")) for s in ss)
        total += chars
        stats[k] = {
            "count": len(ss),
            "chars": chars,
            "titles": [s.title for s in ss if getattr(s, "title", None)],
        }
    return total, stats


def dump_sections(
    sections, out_dir: Path, stem: str, *, write_empty: bool = True
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for sec in sorted(sections, key=lambda s: (getattr(s, "key", "") or "")):
        key = _safe_key(getattr(sec, "key", "") or "unknown")
        text = (getattr(sec, "text", None) or "").strip("\n")
        if not write_empty and not text.strip():
            continue
        p = out_dir / f"{stem}.{key}.md"
        p.write_text(text, encoding="utf-8")
        print(f"📝 wrote slice: {p.name} (len={len(text)})")


def _price_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"ok": False, "reason": "no rows"}
    row = rows[0]
    total_price = row.get("total_price") or row.get("total_price")
    return {
        "ok": True,
        "total_price": total_price,
        "unit_price": row.get("unit_price"),
        "items_count": len(row.get("items") or [])
        if isinstance(row.get("items"), list)
        else None,
        "raw_text": row.get("raw_text"),
        "report_type": row.get("report_type"),
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
    use_bytes: bool = False,   # ⭐ 新增
    head_chars: int = 6000,
    debug_detect: bool = True,
    debug_slice: bool = True,
    debug_extract: bool = True,
    preview_chars: int = 180,
    print_text_preview: bool = False,
    export_markdown: bool = True,
    export_markdown_head: int = 0,  # 0=全文；否则只导出前 N 字
    dump_slices: bool = True,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    patterns = patterns or ["*.doc", "*.docx"]

    files: List[Path] = []
    for pat in patterns:
        files.extend(input_dir.glob(pat))
    files = sorted(
        {p.resolve(): p for p in files}.values(), key=lambda p: p.name.lower()
    )

    print(f"📂 Extract 批测试：{input_dir} patterns={patterns} files={len(files)}")
    print(f"📦 输出: {out_dir}")

    items: List[Dict[str, Any]] = []
    t0 = time.time()

    # ✅ extractor runner（按 default_rulesets 自动选 ruleset）
    llm_config = LLMConfig.from_env()
    runner = RuleEngineExtractorRunner(
        debug=debug_extract,
        model_id=llm_config.model_id,
        base_url=llm_config.base_url,
        api_key=llm_config.api_key,
    )

    for i, f in enumerate(files, 1):
        print("\n" + "-" * 70)
        print(f"▶ [{i}/{len(files)}] {f.name}")

        try:
            # 1) load（doc/docx -> markdown）
            if use_bytes:
                file_bytes = f.read_bytes()
                ctx = pipe.load_bytes(file_bytes, filename=f.name, debug=False)
            else:
                ctx = pipe.load(docx_path=f, debug=False)
            md = ctx.ensure_markdown() or ""

            # 2) detect report_type
            rt = None
            try:
                rt = pipe.step_detect_report_type(
                    ctx, debug=debug_detect, head_chars=head_chars
                )
            except Exception as e:
                print(f"⚠️ detect failed (ignore): {e}")
            rt = rt or (ctx.metadata or {}).get("report_type") or "house"
            print(f"🧠 report_type={rt}")

            # 3) slice（推荐：抽取会更稳）
            slice_ruleset = _pick_slice_ruleset(rt)
            if debug_slice:
                print(f"🧩 slice ruleset={slice_ruleset.name}")

            ctx.metadata = ctx.metadata or {}
            ctx.metadata["debug_slice"] = bool(debug_slice)

            slicer = RuleEngineSlicer(
                debug=debug_slice,
                preview_chars=preview_chars,
                print_text_preview=print_text_preview,
            )
            sections = list(slicer.slice(ctx))
            for s in sections:
                ctx.add_slice(s)
            print(f"🧩 sections={len(sections)}")
            for j, s in enumerate(sections[:8], 1):
                print(
                    f"  - [{j}] key={getattr(s, 'key', None)} title={getattr(s, 'title', None)} "
                    f"len={len(getattr(s, 'text', '') or '')} preview={_preview(getattr(s, 'text', '') or '', 140)}"
                )

            # 4) 导出 markdown（便于排查）
            file_out_dir = out_dir / f.stem
            file_out_dir.mkdir(parents=True, exist_ok=True)

            if export_markdown:
                md_out = file_out_dir / f"{f.stem}.md"
                if export_markdown_head and export_markdown_head > 0:
                    md_out.write_text(md[:export_markdown_head], encoding="utf-8")
                else:
                    md_out.write_text(md, encoding="utf-8")
                print(f"📝 wrote markdown: {md_out.name} (len={len(md)})")

            # 5) dump slices
            if dump_slices:
                slices_dir = file_out_dir / "_slices"
                dump_sections(sections, slices_dir, f.stem, write_empty=True)

            # 6) 抽取（按 default_rulesets 自动选）
            # ✅ 抽取前打印：price 这个 extractor 会使用哪些 keys 的命中情况（方便你定位“为什么跑偏”）
            price_keys = ["summary"]
            total_chars, slice_stats = _sum_slice_chars(ctx, price_keys)

            if debug_extract:
                print("🔎 extract input slice stats (for troubleshooting):")
                for k, st in slice_stats.items():
                    if st["count"] or st["chars"]:
                        print(
                            f"  ✅ key={k:<16} count={st['count']:<2} chars={st['chars']}"
                        )
                if total_chars == 0:
                    print(
                        "  ⚠️ no matched slices in the above keys (will fallback to full if policy=full)."
                    )

            results = runner.run(ctx)

            # 7) 落盘：全量抽取结果
            res_out = file_out_dir / f"{f.stem}.extract.json"
            _write_json(res_out, results)
            print(f"✅ wrote extract: {res_out.name}")

            # 8) 每个 extractor 单独保存
            extract_dir = file_out_dir / "_extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            extract_files = {}

            for slug, rows in (results or {}).items():
                safe_slug = _safe_key(slug)
                out_file = extract_dir / f"{safe_slug}.json"

                _write_json(out_file, rows)

                extract_files[slug] = str(out_file)

                print(f"📦 wrote extractor: {slug} -> {out_file.name} rows={len(rows)}")

                # 如果是 price，额外打印摘要（保留你的调试功能）
                if slug in ("price"):
                    summ = _price_summary(rows)
                    print("💰 price summary:")
                    print(json.dumps(summ, ensure_ascii=False, indent=2))

            # 9) sections 全量 json（可选：和你 slice 批测试一致）
            sec_out = file_out_dir / f"{f.stem}.sections.json"
            sec_payload = {
                "file": f.name,
                "path": str(f),
                "report_type": rt,
                "slice_ruleset": slice_ruleset.name,
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
                    "report_type": rt,
                    "slice_ruleset": slice_ruleset.name,
                    "sections": len(sections),
                    "extract_out": str(res_out),
                    "extractors": extract_files,
                    "ok": True,
                }
            )

        except Exception as e:
            print(f"❌ extract failed: {e}")
            items.append({"file": f.name, "path": str(f), "error": str(e), "ok": False})

    result = {
        "input_dir": str(input_dir),
        "patterns": patterns,
        "total": len(files),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "items": items,
    }

    _write_json(out_dir / "extract.batch.json", result)

    print("\n" + "=" * 70)
    print(f"🏁 extract 完成 | total={result['total']} | ms={result['elapsed_ms']}")
    print(f"📦 汇总输出: {out_dir / 'extract.batch.json'}")
    return result


if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    app_root = current_file.parents[1]  # 按你现有脚本一致（根据你实际层级调整）

    input_dir = app_root / "inputs" / "report_extract"
    out_dir = input_dir / "_outputs"

    # ✅ pipeline：这里只要 load + detect 就够，slicers/extractors 传空
    pipe = ReportPipeline(llm_config=LLMConfig.from_env())

    print("\n===== BYTES MODE =====")

    run_extract_batch(
        input_dir=input_dir,
        out_dir=out_dir / "bytes",
        pipe=pipe,
        patterns=["*.doc", "*.docx"],
        use_bytes=True,
    )
