from __future__ import annotations

import sys
import os
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ✅ 添加项目根目录到 sys.path（按你的项目结构调整）
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fd_extractai_report.pipeline import ReportPipeline

# ✅ 用于定位你实际 import 到的 detect 函数文件（抓“跑的不是你改的那份代码”）
import inspect
 
def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def run_detect_report_type_batch(
    *,
    input_dir: Path,
    pipe: ReportPipeline,
    out_dir: Path,
    patterns: Optional[List[str]] = None,
    head_chars: int = 6000,
    debug: bool = True,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    patterns = patterns or ["*.doc", "*.docx"]

    files: List[Path] = []
    for pat in patterns:
        files.extend(input_dir.glob(pat))

    # 去重 + 排序
    files = sorted({p.resolve(): p for p in files}.values(), key=lambda p: p.name.lower())

    print(f"📂 Detect 批测试：{input_dir}  patterns={patterns}  files={len(files)}")
    print(f"📦 输出: {out_dir}")

 
    items: List[Dict[str, Any]] = []
    t0 = time.time()

    for i, f in enumerate(files, 1):
        print("\n" + "-" * 70)
        print(f"▶ [{i}/{len(files)}] {f.name}")

        try:
            # 1) load（doc/docx -> markdown）
            ctx = pipe.load(docx_path=f, debug=False)

            # 2) detect（只看开头 head_chars）
            rt = pipe.step_detect_report_type(ctx, debug=debug, head_chars=head_chars)

            info = ctx.metadata.get("report_type_debug") or {}

            # ✅ 不要用 `or {}` 吞掉 None，保留原样便于排查
            scores = info.get("scores")
            reason = info.get("reason")
            strong_text = info.get("strong_text")
            strong_hit = info.get("strong_hit")

            print(
                f"🧠 report_type={rt} | reason={reason} | scores={scores} "
                f"| strong_text={strong_text} | strong_hit={strong_hit}"
            )

            items.append(
                {
                    "file": f.name,
                    "path": str(f),
                    "report_type": rt,
                    "reason": reason,
                    "scores": scores,
                    "strong_text": strong_text,
                    "strong_hit": strong_hit,
                    "head_chars": head_chars,
                }
            )

        except Exception as e:
            print(f"❌ detect failed: {e}")
            items.append({"file": f.name, "path": str(f), "error": str(e)})

    result = {
        "input_dir": str(input_dir),
        "patterns": patterns,
        "total": len(files),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "items": items,
    }

    _write_json(out_dir / "report_type.json", result)

    print("\n" + "=" * 70)
    print(f"🏁 detect 完成 | total={result['total']} | ms={result['elapsed_ms']}")
    print(f"📦 输出文件: {out_dir / 'report_type.json'}")
    return result


if __name__ == "__main__":
    current_file = Path(__file__).resolve()
    app_root = current_file.parents[1]  # 你自己确认：tests/xxx.py -> parents[1] 是否为项目根目录

    input_dir = app_root / "inputs" / "report_detect"
    out_dir = input_dir / "_outputs"

    # ✅ 不需要 slicers / extractors
    pipe = ReportPipeline(slicers=[], extractors=[])

    run_detect_report_type_batch(
        input_dir=input_dir,
        pipe=pipe,
        out_dir=out_dir,
        patterns=["*.doc", "*.docx"],
        head_chars=6000,
        debug=True,
    )