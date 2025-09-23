"""Extract structured report details from DOCX files with LangExtract."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from langextract import extract
from langextract.core import data

from app.utils.file_parser import EXPORT_DIR
from config import CONFIG

logger = logging.getLogger(__name__)

try:  # Optional dependency for quick DOCX to text conversion
    import docx2txt  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    docx2txt = None

try:  # Optional dependency for structured DOCX parsing
    from docx import Document  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Document = None  # type: ignore

PROMPT_DESCRIPTION = (
    "你是一名估值分析师。请从提供的估价报告文本中抽取结构化信息。\n"
    "输出字段：\n"
    "1. report_number: 报告编号。\n"
    "2. report_date: 报告时间。\n"
    "3. bank: 银行名称。\n"
    "4. client: 委托人。\n"
    "5. asset: 针对每个标的物创建一条记录，attributes 使用 owner, asset_type, total_price。\n"
    "保持原文格式，无信息时返回空字段，不要猜测。"
)

EXAMPLE_TEXT = (
    "报告编号：HB-2024-001\n"
    "报告时间：2024年8月18日\n"
    "委托人：某某资产管理有限公司\n"
    "银行：中国农业银行北京分行\n"
    "标的物一：住宅，产权人：李四，总价：320万元。\n"
    "标的物二：车位，产权人：王五，总价：35万元。"
)

EXAMPLES: Sequence[data.ExampleData] = [
    data.ExampleData(
        text=EXAMPLE_TEXT,
        extractions=[
            data.Extraction("report_number", "HB-2024-001"),
            data.Extraction("report_date", "2024年8月18日"),
            data.Extraction("bank", "中国农业银行北京分行"),
            data.Extraction("client", "某某资产管理有限公司"),
            data.Extraction(
                "asset",
                "住宅",
                attributes={
                    "owner": "李四",
                    "asset_type": "住宅",
                    "total_price": "320万元",
                },
            ),
            data.Extraction(
                "asset",
                "车位",
                attributes={
                    "owner": "王五",
                    "asset_type": "车位",
                    "total_price": "35万元",
                },
            ),
        ],
    )
]

MODEL_ID = CONFIG.LOCAL_MODEL_NAME
MODEL_URL = CONFIG.LOCAL_MODEL_URL
MAX_PAGES_DEFAULT = 10
PAGE_BREAK_PATTERN = re.compile(r"\f|\x0c")
FIELD_KEYS = {
    "report_number": ("report_number", "报告编号", "编号"),
    "report_date": ("report_date", "报告时间", "时间"),
    "bank": ("bank", "银行"),
    "client": ("client", "委托人", "委托单位"),
    "asset_owner": ("owner", "产权人", "权利人"),
    "asset_type": ("asset_type", "标的物类型", "类型"),
    "asset_total_price": ("total_price", "标的物总价", "总价", "总金额"),
}


@dataclass
class AssetInfo:
    owner: str | None = None
    asset_type: str | None = None
    total_price: str | None = None

    def as_row(self) -> dict[str, str | None]:
        return {
            "asset_owner": self.owner,
            "asset_type": self.asset_type,
            "asset_total_price": self.total_price,
        }


@dataclass
class ReportExtractionResult:
    report_number: str | None = None
    report_date: str | None = None
    bank: str | None = None
    client: str | None = None
    assets: list[AssetInfo] = field(default_factory=list)
    excel_path: Path | None = None

    def base_row(self) -> dict[str, str | None]:
        return {
            "report_number": self.report_number,
            "report_date": self.report_date,
            "bank": self.bank,
            "client": self.client,
        }

    def to_rows(self) -> list[dict[str, str | None]]:
        if not self.assets:
            row = self.base_row()
            row.update({
                "asset_owner": None,
                "asset_type": None,
                "asset_total_price": None,
            })
            return [row]

        rows: list[dict[str, str | None]] = []
        for asset in self.assets:
            row = self.base_row()
            row.update(asset.as_row())
            rows.append(row)
        return rows


def _maybe_api_key() -> str | None:
    """Return the LangExtract API key if one has been configured."""
    return os.getenv("LANGEXTRACT_API_KEY")


def read_docx_text(docx_path: Path, max_pages: int = MAX_PAGES_DEFAULT) -> str:
    """Extract text from a DOCX file, limited to the first ``max_pages`` pages."""
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    if docx2txt:
        text = docx2txt.process(str(docx_path))
        return _trim_to_pages(text, max_pages)

    if Document is None:
        raise ImportError(
            "Parsing DOCX requires either docx2txt or python-docx to be installed."
        )

    return _read_with_python_docx(docx_path, max_pages)


def _trim_to_pages(raw_text: str, max_pages: int) -> str:
    pages = [chunk.strip() for chunk in PAGE_BREAK_PATTERN.split(raw_text) if chunk.strip()]
    if pages:
        return "\n\n".join(pages[:max_pages])
    return raw_text


def _read_with_python_docx(docx_path: Path, max_pages: int) -> str:
    if Document is None:  # pragma: no cover - safety check
        raise ImportError("python-docx is not available")

    document = Document(str(docx_path))
    pages: list[str] = []
    current_lines: list[str] = []

    for block in _iter_block_items(document):
        if isinstance(block, str):  # Table text is returned as a string block
            if block:
                current_lines.append(block)
            continue

        text = block.text.strip()
        if text:
            current_lines.append(text)

        if _paragraph_has_page_break(block):
            if current_lines:
                pages.append("\n".join(current_lines).strip())
                current_lines = []
            if len(pages) >= max_pages:
                break

    if current_lines and len(pages) < max_pages:
        pages.append("\n".join(current_lines).strip())

    return "\n\n".join(pages[:max_pages])


def _iter_block_items(document: "Document") -> Iterable[object]:
    """Yield paragraphs and tables in document order."""
    from docx.oxml.table import CT_Tbl  # type: ignore
    from docx.oxml.text.paragraph import CT_P  # type: ignore
    from docx.table import Table  # type: ignore
    from docx.text.paragraph import Paragraph  # type: ignore

    for child in document.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield _table_to_text(Table(child, document))


def _paragraph_has_page_break(paragraph: object) -> bool:
    try:
        runs = paragraph.runs  # type: ignore[attr-defined]
    except AttributeError:
        return False

    for run in runs:
        for br in run._element.findall(".//w:br", run._element.nsmap):  # type: ignore[attr-defined]
            br_type = br.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type")
            if br_type == "page":
                return True
    return False


def _table_to_text(table: "Table") -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        if any(cells):
            rows.append(" | ".join(filter(None, cells)))
    return "\n".join(rows)


def _extract_field(attributes: dict[str, str], keys: Sequence[str], fallback: str | None) -> str | None:
    for key in keys:
        value = attributes.get(key)
        if value:
            return value.strip()
    if fallback:
        return fallback.strip()
    return None


def _populate_result(result: ReportExtractionResult, extractions: Iterable[data.Extraction]) -> None:
    for extraction in extractions:
        label = (extraction.extraction_class or "").lower()
        text_value = (extraction.extraction_text or "").strip() or None
        attributes = extraction.attributes or {}

        if label == "asset":
            owner = _extract_field(attributes, FIELD_KEYS["asset_owner"], None)
            asset_type = _extract_field(attributes, FIELD_KEYS["asset_type"], text_value)
            total_price = _extract_field(attributes, FIELD_KEYS["asset_total_price"], None)
            result.assets.append(AssetInfo(owner=owner, asset_type=asset_type, total_price=total_price))
            continue

        if label in ("report_number", "report_date", "bank", "client"):
            current_value = getattr(result, label)
            if current_value:
                continue
            keys = FIELD_KEYS[label]
            value = _extract_field(attributes, keys, text_value)
            if value:
                setattr(result, label, value)


def _rows_to_excel(rows: Sequence[dict[str, str | None]], destination: Path) -> Path:
    if not rows:
        raise ValueError("No rows available for export")

    destination.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(destination, index=False, engine="openpyxl")
    return destination


def process_report(docx_path: str, output_name: str | None = None, max_pages: int = MAX_PAGES_DEFAULT) -> ReportExtractionResult:
    """
    Parse the first ``max_pages`` of the DOCX report, run LangExtract, and export to Excel.

    Args:
        docx_path: Path to the DOCX appraisal report.
        output_name: Optional Excel file name. Defaults to ``<docx_stem>_extraction_<timestamp>.xlsx``.
        max_pages: Limit the amount of text sent to the model.

    Returns:
        ReportExtractionResult populated with structured data and the Excel export path.
    """
    source_path = Path(docx_path).expanduser().resolve()
    text = read_docx_text(source_path, max_pages=max_pages)

    extract_kwargs = {
        "text_or_documents": text,
        "prompt_description": PROMPT_DESCRIPTION,
        "examples": EXAMPLES,
        "format_type": data.FormatType.JSON,
        "max_char_buffer": 4000,
        "model_id": MODEL_ID,
        "model_url": MODEL_URL,
    }

    api_key = _maybe_api_key()
    if api_key:
        extract_kwargs["api_key"] = api_key

    annotated_doc = extract(**extract_kwargs)
    result = ReportExtractionResult()
    extractions: Iterable[data.Extraction] = annotated_doc.extractions or []
    _populate_result(result, extractions)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_name:
        excel_name = output_name
    else:
        excel_name = f"{source_path.stem}_extraction_{timestamp}.xlsx"

    destination = EXPORT_DIR / excel_name
    rows = result.to_rows()
    result.excel_path = _rows_to_excel(rows, destination)
    logger.info("Report extraction exported to %s", result.excel_path)

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Extract appraisal report details to Excel.")
    parser.add_argument("docx", help="Path to the DOCX report")
    parser.add_argument("--output", help="Optional Excel file name")
    parser.add_argument("--pages", type=int, default=MAX_PAGES_DEFAULT, help="Number of pages to read")
    args = parser.parse_args()

    result = process_report(args.docx, output_name=args.output, max_pages=args.pages)
    print("报告编号:", result.report_number)
    print("报告时间:", result.report_date)
    print("银行:", result.bank)
    print("委托人:", result.client)
    print(f"结果已导出: {result.excel_path}")


if __name__ == "__main__":
    main()
