from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/fd-extractai-report/src"))

if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fd_extractai_report.converters.markdown_converter import (
    MarkdownConvertOptions,
    MarkdownFileConverter,
)
from fd_extractai_report.settings import LLMConfig


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_llm_config(enable_ocr: bool | None) -> LLMConfig:
    llm_config = LLMConfig.from_env()
    if not llm_config.api_key and llm_config.base_url:
        llm_config = replace(llm_config, api_key="EMPTY")
    if not llm_config.ocr_api_key and (llm_config.ocr_base_url or llm_config.base_url):
        llm_config = replace(llm_config, ocr_api_key="EMPTY")
    if enable_ocr is None:
        return llm_config
    return replace(llm_config, enable_ocr=enable_ocr)


def run_text_extract(
    *,
    file_path: Path,
    out_dir: Path,
    use_bytes: bool,
    enable_ocr: bool | None,
) -> dict[str, Any]:
    llm_config = _build_llm_config(enable_ocr)
    converter = MarkdownFileConverter(
        options=MarkdownConvertOptions(enable_ocr=llm_config.enable_ocr),
        llm_config=llm_config,
    )

    if use_bytes:
        markdown_text = converter.convert(file_path.read_bytes(), filename=file_path.name)
    else:
        markdown_text = converter.convert(file_path)

    out_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = out_dir / f"{file_path.stem}.md"
    summary_path = out_dir / f"{file_path.stem}.summary.json"

    markdown_path.write_text(markdown_text, encoding="utf-8")

    summary = {
        "file": file_path.name,
        "path": str(file_path),
        "use_bytes": use_bytes,
        "enable_ocr": llm_config.enable_ocr,
        "chars": len(markdown_text),
        "image_ocr_markers": markdown_text.count("[Image OCR]"),
        "output": str(markdown_path),
    }
    _write_json(summary_path, summary)

    print(f"input={file_path}")
    print(f"use_bytes={use_bytes}")
    print(f"enable_ocr={llm_config.enable_ocr}")
    print(f"chars={len(markdown_text)}")
    print(f"image_ocr_markers={summary['image_ocr_markers']}")
    print(f"markdown={markdown_path}")
    print(f"summary={summary_path}")
    print(markdown_text[:1000])

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Direct text extraction for jd inputs.")
    parser.add_argument(
        "input",
        nargs="?",
        default=str(ROOT / "inputs" / "jd" / "t_1.docx"),
        help="Input document path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "inputs" / "jd" / "_outputs" / "t_1_text",
        help="Output directory.",
    )
    parser.add_argument(
        "--bytes",
        action="store_true",
        help="Convert via bytes API.",
    )
    parser.add_argument(
        "--enable-ocr",
        action="store_true",
        help="Force enable OCR for this run.",
    )
    parser.add_argument(
        "--disable-ocr",
        action="store_true",
        help="Force disable OCR for this run.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.enable_ocr and args.disable_ocr:
        parser.error("`--enable-ocr` and `--disable-ocr` cannot be used together.")

    enable_ocr: bool | None = None
    if args.enable_ocr:
        enable_ocr = True
    elif args.disable_ocr:
        enable_ocr = False

    file_path = Path(args.input).resolve()
    out_dir = args.out_dir.resolve()

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    run_text_extract(
        file_path=file_path,
        out_dir=out_dir,
        use_bytes=bool(args.bytes),
        enable_ocr=enable_ocr,
    )


if __name__ == "__main__":
    main()
