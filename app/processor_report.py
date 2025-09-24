"""Extract structured report details from DOCX files with LangExtract."""

from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence, Iterable, Any, Dict,List, Union,Tuple
from app.utils.prompt_utils import load_prompt

import pandas as pd
from langextract import extract
from langextract.core import data
from dataclasses import asdict, is_dataclass
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

PROMPT_DESCRIPTION = load_prompt("gen_con_data.txt")

example_1 = data.ExampleData(
        text= """估价报告编号：	湘经典（2025）衡房011809A
估价项目名称：	雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估
估价委托人：	长沙银行股份有限公司
房地产估价机构：	湖南经典房地产评估咨询有限公司
注册房地产估价师：	马庄  	注册号：4320240054
	李萍  	注册号：4320040057
估价报告出具日期：	2025年09月16日""",
        extractions=[
            data.Extraction("report_number", "湘经典（2025）衡房011809A"),
            data.Extraction("project_name", "雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估"),
            data.Extraction("client_name", "长沙银行股份有限公司"),
            data.Extraction("report_date", "2025年09月16日"),
            data.Extraction("appraiser", "马庄  注册号：4320240054", attributes={ "appraiser":"马庄", "register_id": "4320240054"}),
            data.Extraction("appraiser", "李萍  注册号：4320040057", attributes={"appraiser":"李萍", "register_id": "4320040057"})            
        ],
    )

example_2 = data.ExampleData(
        text= """本公司根据估价目的，遵循估价原则，采用科学合理的估价方法，在认真分析现有资料的基础上，经过测算，结合估价经验与对影响房地产市场价格因素进行分析，确定估价对象在市场上有足够的买方和卖方，并且进入市场无障碍的条件下，于价值时点的假定未设立法定优先受偿权下的市场价值单价为20105元/平方米，总价为4408825元，估价师知悉的法定优先受偿款为0元，最后确定委评房地产的抵押价值单价为20105元/平方米，总价为4408825元（大写：人民币肆佰肆拾万捌仟捌佰贰拾伍元整)。估价结果汇总如下表所示。""",
        extractions=[
            data.Extraction("unit_price", "20105"),                        
            data.Extraction("total_price", "4408825"),                      
        ],
    )
 

example_3 = data.ExampleData(
        text= """估价对象基本情况一览表
估价对象	坐落	估价对象范围	所在层次/总层数	规划用途	权证号码	产权人	建筑面积（㎡）
1	洪江市黔城镇玉壶路交通局隔壁01、02等2套	房屋及其占用范围内的土地和其他不动产	1/6	商业	洪房权证黔城镇字第711000391号	肖春梅	61.99
2	洪江市黔城镇玉壶路交通局隔壁03、04等2套	房屋及其占用范围内的土地和其他不动产	1/6	商业	洪房权证黔城镇字第711000390号	肖春梅	61.99
3	洪江市黔城镇玉壶路（交通局隔壁）	房屋及其占用范围内的土地和其他不动产	1/6	商业	洪房权证黔城字第715001640号	肖春梅	77.04
""",
        extractions=[
            data.Extraction(extraction_class="object",
            extraction_text="1 洪江市黔城镇玉壶路交通局隔壁01、02等2套 房屋及其占用范围内的土地和其他不动产 1/6 商业 洪房权证黔城镇字第7110003肖 61.99",
            attributes={
                "item_number": "1",
                "location": "洪江市黔城镇玉壶路交通局隔壁01、02等2套",
                "scope": "房屋及其占用范围内的土地和其他不动产",
                "floor_info": "1/6",
                "purpose": "商业",
                "certificate_number": "洪房权证黔城镇字第7110003",
                "owner": "肖春梅",
                "area": "61.99"
            },),
            data.Extraction( extraction_class="object",
            extraction_text="2 洪江市黔城镇玉壶路交通局隔壁03、04等2套 房屋及其占用范围内的土地和其他不动产 1/6 商业 洪房权证黔城镇字第7110000号 肖 61.99",
            attributes={
                "item_number": "2",
                "location": "洪江市黔城镇玉壶路交通局隔壁03、04等2套",
                "scope": "房屋及其占用范围内的土地和其他不动产",
                "floor_info": "1/6",
                "purpose": "商业",
                "certificate_number": "洪房权证黔城镇字第7110000号",
                "owner": "肖春梅",
                "area": "61.99"
            }),
            data.Extraction(extraction_class="object",
            extraction_text="3 洪江市黔城镇玉壶路（交通局隔壁） 房屋及其占用范围内的土地和其他不动产 1/6 商业 洪房权证黔城字第7150010号 肖春77.04",
            attributes={
                "item_number": "3",
                "location": "洪江市黔城镇玉壶路（交通局隔壁）",
                "scope": "房屋及其占用范围内的土地和其他不动产",
                "floor_info": "1/6",
                "purpose": "商业",
                "certificate_number": "洪房权证黔城字第7150010号",
                "owner": "肖春梅",
                "area": "77.04"
            },)           
        ],
    )

EXAMPLES: Sequence[data.ExampleData] = [example_1,example_2,example_3]

MODEL_ID = CONFIG.LOCAL_MODEL_NAME
MODEL_URL = CONFIG.LOCAL_MODEL_URL
MAX_PAGES_DEFAULT = 10
PAGE_BREAK_PATTERN = re.compile(r"\f|\x0c")


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


def _rows_to_excel(rows: Sequence[dict[str, str | None]], destination: Path) -> Path:
    if not rows:
        raise ValueError("No rows available for export")

    destination.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_excel(destination, index=False, engine="openpyxl")
    return destination

def _to_plain_dict(e: Any) -> Dict[str, Any]:
    """把 data.Extraction 或类似对象转成可序列化 dict"""
    # 优先尝试 dataclass
    if is_dataclass(e):
        d = asdict(e)
    else:
        # 宽松兼容：有属性则 getattr；字典则直接用
        if isinstance(e, dict):
            d = dict(e)
        else:
            d = {
                "extraction_class": getattr(e, "extraction_class", None),
                "extraction_text": getattr(e, "extraction_text", None),
                "attributes": getattr(e, "attributes", None),
                "confidence": getattr(e, "confidence", None),
                "spans": getattr(e, "spans", None) or getattr(e, "span", None),
            }
    # 兜底键位
    d.setdefault("attributes", {})
    d.setdefault("confidence", None)
    # 兼容单数 span
    if "spans" not in d and "span" in d:
        d["spans"] = d.pop("span")
    return d

def _rows_for_sheet(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    把一批抽取 dict -> DataFrame：
    固定列：class/text/confidence/spans_json
    动态列：attributes.* 铺平，保留 attributes._evidence 到 evidence_json
    """
    meta_rows, attr_rows = [], []
    for idx, r in enumerate(records, start=1):
        attrs = r.get("attributes") or {}
        ev = None
        if isinstance(attrs, dict) and "_evidence" in attrs:
            ev = attrs.pop("_evidence")  # 从 attributes 拿出属性级证据

        meta_rows.append({
            "#": idx,
            "extraction_class": r.get("extraction_class"),
            "extraction_text": r.get("extraction_text"),
            "confidence": r.get("confidence"),
            "spans_json": json.dumps(r.get("spans"), ensure_ascii=False) if r.get("spans") else None,
            "attr_evidence_json": json.dumps(ev, ensure_ascii=False) if ev else None,
        })
        # attributes 铺平
        attr_rows.append(attrs if isinstance(attrs, dict) else {"attributes": attrs})

    df_meta = pd.DataFrame(meta_rows)
    df_attr = pd.json_normalize(attr_rows, sep=".")
    df = pd.concat([df_meta, df_attr], axis=1)
    return df



def export_extractions_to_excel(
    extractions: Iterable[Union[Dict[str, Any], Any]],
    path: str = "extractions.xlsx",
    split_by_class: bool = True,
    include_raw_sheet: bool = True,
) -> str:
    """
    将 LangExtract 的 extractions 导出为 Excel。
    - split_by_class=True：按 extraction_class 分工作表；否则汇总到一个表。
    - include_raw_sheet=True：附加 raw_json 工作表保留原始记录（便于审计/复算）。
    返回：生成的 Excel 路径。
    """
    # 标准化为 dict 列表
    records = [_to_plain_dict(e) for e in (extractions or [])]
    if not records:
        # 建一个空表也写出去
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            pd.DataFrame({"info": ["no extractions"]}).to_excel(writer, index=False, sheet_name="extractions")
        return path

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        if split_by_class:
            # 分组写表：每个 class 一个 sheet
            by_cls: Dict[str, List[Dict[str, Any]]] = {}
            for r in records:
                cls = r.get("extraction_class") or "UNKNOWN"
                by_cls.setdefault(cls, []).append(r)
            # 控制工作表名长度（Excel 限 31）
            for cls, recs in by_cls.items():
                sheet = cls[:31] if cls else "UNKNOWN"
                _rows_for_sheet(recs).to_excel(writer, index=False, sheet_name=sheet)
        else:
            # 汇总写到单表
            _rows_for_sheet(records).to_excel(writer, index=False, sheet_name="extractions")

        if include_raw_sheet:
            raw_rows = [{"json": json.dumps(r, ensure_ascii=False)} for r in records]
            pd.DataFrame(raw_rows).to_excel(writer, index=False, sheet_name="raw_json")

        # 可选：自动列宽（对所有 sheet）
        for ws in writer.sheets.values():
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(12, max_len + 2), 60)

    return path


def _norm_attrs(attrs: Dict) -> Tuple:
    """规范化 attributes 用于比对：去掉 _evidence/空值，键排序成不可变元组"""
    if not isinstance(attrs, dict):
        return (("value", attrs),)
    pruned = {k:v for k,v in attrs.items() if k not in {"_evidence"} and v not in (None, "", [])}
    # 将嵌套 dict/list 转 JSON 字符串再比对，避免顺序影响
    return tuple(sorted((k, json.dumps(v, ensure_ascii=False, sort_keys=True)) for k,v in pruned.items()))

def _get_span_page(e) -> int | None:
    s = getattr(e, "spans", None) or getattr(e, "span", None)
    if isinstance(s, dict):
        return s.get("page")
    if isinstance(s, list) and s and isinstance(s[0], dict):
        return s[0].get("page")
    return None


def dedupe_extractions(extractions: Iterable[Any]) -> List[Any]:
    """
    去重策略：
    1) 同类 + attributes 完全等价 -> 留最高置信度
    2) 否则，同类 + extraction_text 完全相同 -> 留最高置信度
    3) 否则，同类 + 同页 且 文本相似度高（这里用简单规范化后完全相等）-> 留最高置信度
    其余保留。
    """
    items = list(extractions or [])
    if not items:
        return items

    # 预处理：抽常用字段
    def rec(e):
        cls = getattr(e, "extraction_class", None)
        txt = (getattr(e, "extraction_text", None) or "").strip()
        # 轻度规范化文本（去多空白/全角空格）
        txt_norm = re.sub(r"\s+", " ", txt.replace("\u3000", " ")).strip()
        attrs = getattr(e, "attributes", None) or {}
        attrs_key = _norm_attrs(attrs)
        conf = getattr(e, "confidence", None) or 0.0
        page = _get_span_page(e)
        return cls, txt, txt_norm, attrs, attrs_key, conf, page

    # 分三轮去重
    kept: Dict[Tuple, Any] = {}
    seen_keys = set()

    # 轮1：同类 + attrs 完全等价
    for e in items:
        cls, txt, txt_norm, attrs, attrs_key, conf, page = rec(e)
        if cls is None:
            continue
        key1 = ("K1", cls, attrs_key)
        best = kept.get(key1)
        if best is None or (getattr(e, "confidence", 0) or 0) > (getattr(best, "confidence", 0) or 0):
            kept[key1] = e
        seen_keys.add((cls, id(e)))

    # 轮2：同类 + 原始文本完全一致（仅当没被轮1命中/替换）
    for e in items:
        cls, txt, txt_norm, attrs, attrs_key, conf, page = rec(e)
        if cls is None:
            continue
        key1 = ("K1", cls, attrs_key)
        if kept.get(key1) is e:
            continue
        key2 = ("K2", cls, txt)
        best = kept.get(key2)
        if best is None or conf > (getattr(best, "confidence", 0) or 0):
            kept[key2] = e

    # 轮3：同类 + 同页 + 规范化文本一致（容忍空白差异）
    for e in items:
        cls, txt, txt_norm, attrs, attrs_key, conf, page = rec(e)
        if cls is None:
            continue
        key1 = ("K1", cls, attrs_key); key2 = ("K2", cls, txt)
        if kept.get(key1) is e or kept.get(key2) is e:
            continue
        key3 = ("K3", cls, page, txt_norm)
        best = kept.get(key3)
        if best is None or conf > (getattr(best, "confidence", 0) or 0):
            kept[key3] = e

    # 汇总保留项
    deduped = list({id(v): v for v in kept.values()}.values())
    return deduped

def process_report(docx_path: str, output_name: str | None = None, max_pages: int = MAX_PAGES_DEFAULT) -> str:
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
        "prompt_description": """从评估报告中提取以下结构化信息。提取的信息必须严格来自报告原文，不要进行概括或转述。""",
        "examples": EXAMPLES,
        "format_type": data.FormatType.JSON,
        "max_char_buffer": 4000,        
    }

    api_key = _maybe_api_key()
    if api_key:
        extract_kwargs["api_key"] = api_key

    annotated_doc = extract(**extract_kwargs)

    extractions: Iterable[data.Extraction] = annotated_doc.extractions or []
    #_populate_result(result, extractions)
    extractions = dedupe_extractions(extractions)   # <<—— 新增
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_name:
        excel_name = output_name
    else:
        excel_name = f"{source_path.stem}_extraction_{timestamp}.xlsx"
    
    destination = EXPORT_DIR / excel_name
    path = extractions_to_excel(extractions, out_path=destination)
    return path

def _flatten_attributes(rows_attrs: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """把多条 Extraction 的 attributes 动态铺平为列（不存在的键补 NaN）"""
    # 用 json_normalize 可以应对嵌套结构（如 dict/list）
    df = pd.json_normalize(list(rows_attrs), sep=".")
    # 若 attributes 为空列表/全 None，给一个空 DataFrame
    return df if not df.empty else pd.DataFrame()

def extractions_to_excel(extractions: Iterable, out_path: str = "extractions.xlsx") -> str:
    """
    将 LangExtract 的 extractions 导出为 Excel。
    - Sheet1: 扁平化后的表格（extraction_class/extraction_text/attributes展开…）
    - Sheet2: 原始JSON（逐行，便于审计）
    """
    rows_meta = []
    rows_attrs = []

    for idx, e in enumerate(extractions or [], start=1):
        # 兼容不同版本字段名：常见的有 extraction_class / extraction_text / attributes / confidence / spans 等
        extraction_class = getattr(e, "extraction_class", None)
        extraction_text  = getattr(e, "extraction_text", None)
        attributes       = getattr(e, "attributes", None) or {}
        confidence       = getattr(e, "confidence", None)
        spans            = getattr(e, "spans", None) or getattr(e, "span", None)  # 有的实现是单数

        rows_meta.append({
            "#": idx,
            "extraction_class": extraction_class,
            "extraction_text": extraction_text,
            "confidence": confidence,
            # 把 spans 存成紧凑 JSON，避免列爆炸；若你只关心 page/start/end，可在此挑字段
            "spans_json": json.dumps(spans, ensure_ascii=False) if spans else None
        })
        rows_attrs.append(attributes)  

    # 基础元信息 DataFrame
    df_meta = pd.DataFrame(rows_meta)

    # attributes 动态铺平
    df_attr = _flatten_attributes(rows_attrs)

    # 合并：左侧是固定列，右侧是 attributes 展平列
    if not df_attr.empty:
        df = pd.concat([df_meta, df_attr], axis=1)
    else:
        df = df_meta

    # 另备一份“原始 JSON”便于审计/复算
    raw_json_lines = []
    for e in (extractions or []):
        try:
            # 尝试把对象转 dict；若不支持，退回手动拼装
            raw = {
                "extraction_class": getattr(e, "extraction_class", None),
                "extraction_text": getattr(e, "extraction_text", None),
                "attributes": getattr(e, "attributes", None),
                "confidence": getattr(e, "confidence", None),
                "spans": getattr(e, "spans", None) or getattr(e, "span", None),
            }
        except Exception:
            raw = str(e)
        raw_json_lines.append({"json": json.dumps(raw, ensure_ascii=False)})

    df_raw = pd.DataFrame(raw_json_lines)

    # 写 Excel（带两个工作表）
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="extractions")
        df_raw.to_excel(writer, index=False, sheet_name="raw_json")

        # 调整列宽（可选）
        ws = writer.sheets["extractions"]
        for col_cells in ws.columns:
            max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max(12, max_len + 2), 60)

    return out_path
# def main() -> None:
#     import argparse

#     parser = argparse.ArgumentParser(description="Extract appraisal report details to Excel.")
#     parser.add_argument("docx", help="Path to the DOCX report")
#     parser.add_argument("--output", help="Optional Excel file name")
#     parser.add_argument("--pages", type=int, default=MAX_PAGES_DEFAULT, help="Number of pages to read")
#     args = parser.parse_args()

#     result = process_report(args.docx, output_name=args.output, max_pages=args.pages)
#     print("报告编号:", result.report_number)
#     print("报告时间:", result.report_date)
#     print("银行:", result.bank)
#     print("委托人:", result.client)
#     print(f"结果已导出: {result.excel_path}")


# if __name__ == "__main__":
#     main()
