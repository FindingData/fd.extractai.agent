from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/fd-extractai-report/src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fd_extractai_report.converters.markdown_converter import (
    MarkdownConvertOptions,
    MarkdownFileConverter,
)
from fd_extractai_report.settings import LLMConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug Markdown OCR conversion.")
    parser.add_argument("input", type=Path, help="Input document path.")
    parser.add_argument(
        "--bytes",
        action="store_true",
        help="Convert via bytes API instead of file path API.",
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
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output markdown path.",
    )
    return parser


def build_converter(enable_ocr: bool | None) -> MarkdownFileConverter:
    llm_config = LLMConfig.from_env()
    options = MarkdownConvertOptions(enable_ocr=enable_ocr)
    return MarkdownFileConverter(options=options, llm_config=llm_config)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.enable_ocr and args.disable_ocr:
        parser.error("`--enable-ocr` and `--disable-ocr` cannot be used together.")

    enable_ocr: bool | None = None
    if args.enable_ocr:
        enable_ocr = True
    elif args.disable_ocr:
        enable_ocr = False

    converter = build_converter(enable_ocr=enable_ocr)
    input_path = args.input.resolve()

    if args.bytes:
        markdown = converter.convert(input_path.read_bytes(), filename=input_path.name)
    else:
        markdown = converter.convert(input_path)

    output_path = args.output or input_path.with_suffix(input_path.suffix + ".md")
    output_path.write_text(markdown, encoding="utf-8")

    print(f"input={input_path}")
    print(f"output={output_path}")
    print(f"chars={len(markdown)}")
    print(markdown[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
