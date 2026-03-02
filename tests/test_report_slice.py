from __future__ import annotations

import sys
import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.report.pipeline import ReportPipeline

# ✅ 你已有的 ruleset / slicer
from app.report.sections.rule_engine_slicer import RuleEngineSlicer
from app.report.rules.slicing.default_rulesets import (
    ruleset_house,
    ruleset_land,
    ruleset_asset,
)

def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def _pick_ruleset(report_type: str):
    # 这里按你项目 report_type 命名改一下即可
    rt = (report_type or "").lower()
    if "house" in rt  in rt:
        return ruleset_house
    if "land" in rt in rt:
        return ruleset_land
    if "asset" in rt in rt:
        return ruleset_asset
    # 兜底：默认按 house（你也可以选择 raise）
    return ruleset_house

def run_slice_sections_batch(
    *,
    input_dir: Path,
    out_dir: Path,
    pipe: ReportPipeline,
    patterns: Optional[List[str]] = None,
    head_chars: int = 6000,
    debug_detect: bool = True,
    debug_slice: bool = True,
    preview_chars: int = 180,
    print_text_preview: bool = False,
    export_markdown: bool = True,
export_markdown_head: int = 0,   
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    patterns = patterns or ["*.doc", "*.docx"]

    files: List[Path] = []
    for pat in patterns:
        files.extend(input_dir.glob(pat))
    files = sorted({p.resolve(): p for p in files}.values(), key=lambda p: p.name.lower())

    print(f"📂 Slice 批测试：{input_dir} patterns={patterns} files={len(files)}")
    print(f"📦 输出: {out_dir}")

    items: List[Dict[str, Any]] = []
    t0 = time.time()

    for i, f in enumerate(files, 1):
        print("\n" + "-" * 70)
        print(f"▶ [{i}/{len(files)}] {f.name}")

        try:
            # 1) load（doc/docx -> markdown）
            ctx = pipe.load(docx_path=f, debug=False)

            # 2) detect（可选，但推荐：自动选择 ruleset）
            rt = None
            try:
                rt = pipe.step_detect_report_type(ctx, debug=debug_detect, head_chars=head_chars)
            except Exception as e:
                print(f"⚠️ detect failed (ignore): {e}")

            ruleset = _pick_ruleset(rt or "")
            print(f"🧠 report_type={rt} -> ruleset={ruleset.name}")

            # 3) slice
            ctx.metadata = ctx.metadata or {}
            ctx.metadata["debug_slice"] = bool(debug_slice)

            slicer = RuleEngineSlicer(
                ruleset,
                debug=debug_slice,
                preview_chars=preview_chars,
                print_text_preview=print_text_preview,
            )

            sections = list(slicer.slice(ctx))

            print(f"🧩 sections={len(sections)}")
            for j, s in enumerate(sections[:10], 1):
                # 只预览前 10 个，避免刷屏
                txt = (s.text or "").replace("\n", "\\n")
                txt = txt[:160] + ("..." if len(txt) > 160 else "")
                print(f"  - [{j}] key={s.key} title={s.title} len={len(s.text or '')}  preview={txt}")

                # 0) 拿到 markdown
                md = ctx.ensure_markdown()
                def _probe(label, patterns, text):
                    print(f"🔎 probe {label}:")
                    for s in patterns:
                        try:
                            pat = re.compile(s, re.I | re.M)
                            m = pat.search(text)
                            if m:
                                print(f"  ✅ hit pos={m.start()} pat={s}")
                            else:
                                print(f"  ❌ miss pat={s}")
                        except re.error as e:
                            print(f"  💥 regex error pat={s} err={e}")
                step = ruleset.steps[0]
                starts = step.targets
                ends = (step.params or {}).get("ends") or []
                _probe("starts", starts, md)
                _probe("ends", ends, md)
                # ✅ 输出 markdown 到 output（便于调试）
                if export_markdown:
                    md_file = out_dir / f"{f.stem}.md"
                    md_file.write_text(md or "", encoding="utf-8")
                    print(f"📝 wrote markdown: {md_file}")

                def _safe_key(key: str) -> str:
                # 文件名安全：只保留字母数字下划线中横线点
                    key = key or "unknown"
                    return re.sub(r"[^0-9a-zA-Z_\-\.]+", "_", key).strip("_") or "unknown"

                def dump_sections(sections, out_dir: Path, stem: str, *, write_empty: bool = True) -> None:
                    out_dir.mkdir(parents=True, exist_ok=True)

                    # 按 key 排序，输出更稳定
                    for sec in sorted(sections, key=lambda s: (s.key or "")):
                        key = _safe_key(getattr(sec, "key", "") or "unknown")
                        text = (getattr(sec, "text", None) or "").strip("\n")

                        if not write_empty and not text.strip():
                            continue

                        # 你也可以换成 .txt / .md，看你后续怎么读
                        p = out_dir / f"{stem}.{key}.md"
                        p.write_text(text, encoding="utf-8")

                        # 打印简要信息（长度/是否空）
                        print(f"📝 wrote slice: {p}  (len={len(text)})")
            # 4) dump
            dump_sections(sections, out_dir, f.stem, write_empty=True)
            out_file = out_dir / f"{f.stem}.sections.json"
            payload = {
                "file": f.name,
                "path": str(f),
                "report_type": rt,
                "ruleset": ruleset.name,
                "sections": [
                    {
                        "key": s.key,
                        "title": s.title,
                        "len": len(s.text or ""),
                        "text": s.text,
                        "metadata": s.metadata or {},
                    }
                    for s in sections
                ],
            }
            _write_json(out_file, payload)
            print(f"✅ wrote: {out_file}")

            items.append(
                {
                    "file": f.name,
                    "path": str(f),
                    "report_type": rt,
                    "ruleset": ruleset.name,
                    "sections": len(sections),
                    "out": str(out_file),
                }
            )

        except Exception as e:
            print(f"❌ slice failed: {e}")
            items.append({"file": f.name, "path": str(f), "error": str(e)})

    result = {
        "input_dir": str(input_dir),
        "patterns": patterns,
        "total": len(files),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "items": items,
    }

    _write_json(out_dir / "sections.batch.json", result)

    print("\n" + "=" * 70)
    print(f"🏁 slice 完成 | total={result['total']} | ms={result['elapsed_ms']}")
    print(f"📦 汇总输出: {out_dir / 'sections.batch.json'}")
    return result


if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    app_root = current_file.parents[1]  # 按你现有 detect 脚本一致

    input_dir = app_root / "inputs" / "report_slice"
    out_dir = input_dir / "_outputs"

    # ✅ 不需要 pipeline 里的 slicers/extractors
    pipe = ReportPipeline(slicers=[], extractors=[])

    run_slice_sections_batch(
        input_dir=input_dir,
        out_dir=out_dir,
        pipe=pipe,
        patterns=["*.doc", "*.docx"],
        head_chars=6000,
        debug_detect=True,
        debug_slice=True,
        preview_chars=180,
        print_text_preview=False,  # 你要看 base preview 再开
        export_markdown=True,
        export_markdown_head=8000,
    )