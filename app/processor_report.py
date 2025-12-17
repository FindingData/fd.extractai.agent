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
import pandas as pd
import langextract as lx
from langextract.core import data
from app.utils.file_parser import EXPORT_DIR
from config import CONFIG

logger = logging.getLogger(__name__)



example_valuation_result = data.ExampleData(
    text="""
| 估价对象 | 权证号 | 权利人 | 坐落 | 用途 | 所在层/总层数 | 建筑面积（m2） | 单价（元/m2) | 总价（元） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 洪房权证黔城镇字第711000391号 | 肖春梅 | 洪江市黔城镇玉壶路交通局隔壁01、02等2套 | 商业 | 1/6 | 61.99 | 3535 | 219135 |
| 2 | 洪房权证黔城镇字第711000390号 | 肖春梅 | 洪江市黔城镇玉壶路交通局隔壁03、04等2套 | 商业 | 1/6 | 61.99 | 3535 | 219135 |
| 3 | 洪房权证黔城字第715001640号 | 肖春梅 | 洪江市黔城镇玉壶路（交通局隔壁） | 商业 | 1/6 | 77.04 | 3535 | 272336 |
| 4 | 洪房权证黔字第2009-0878号 | 徐文相 | 洪江市黔城镇玉壶路（交通局隔壁）111、112 | 商业 | 1/6 | 77.04 | 3535 | 272336 |
""",
    extractions=[
       # 仅定义第一条记录的结构
        data.Extraction(
            "valuation_target_item", 
            "洪房权证黔城镇字第711000391号", # 锚点：权证号
            attributes={ 
                "object_num":"估价对象1",
                "certificate_number": "洪房权证黔城镇字第711000391号",
                "owner_name": "肖春梅",
                "building_area": 61.99, # 建议使用数字类型
                "usage": "商业",
                "total_price": 219135
            }
        )
    ]
)  


def extract_valuation_data(md_text) -> str:
    """
    Parse the first ``max_pages`` of the DOCX report, run LangExtract, and export to Excel.

    Args:
        docx_path: Path to the DOCX appraisal report.
        output_name: Optional Excel file name. Defaults to ``<docx_stem>_extraction_<timestamp>.xlsx``.
        max_pages: Limit the amount of text sent to the model.

    Returns:
        ReportExtractionResult populated with structured data and the Excel export path.
    """    
    EXAMPLES: Sequence[data.ExampleData] = [example_valuation_result]
    prompt = """
    请从提供的 Markdown 表格中提取**所有行**的估价对象信息。
    每一行数据必须对应一个独立的 'valuation_target_item' 对象。
    请确保将表格中的 '权证号' 作为抽取文本(extraction_text)，
    并将所有关键信息填充到以下属性中：certificate_number, owner_name, building_area, usage, total_price。
     """
    annotated_doc = lx.extract(
        md_text,
        prompt_description=prompt,
        examples=EXAMPLES,                
        model_id=CONFIG.LOCAL_MODEL_NAME,
        model_url=CONFIG.LOCAL_MODEL_URL,
        max_char_buffer=8192,        
        language_model_params={
            "num_ctx": 18000,
            "timeout": 10*60,
        }
    )

    extractions: Iterable[data.Extraction] = annotated_doc.extractions or []
    # 提取每一项的 attributes，并过滤掉空值
    pure_attributes = [
        e.attributes for e in extractions 
        if hasattr(e, 'attributes') and e.attributes
    ]        
    return pure_attributes

def _flatten_attributes(rows_attrs: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """把多条 Extraction 的 attributes 动态铺平为列（不存在的键补 NaN）"""
    # 用 json_normalize 可以应对嵌套结构（如 dict/list）
    df = pd.json_normalize(list(rows_attrs), sep=".")
    # 若 attributes 为空列表/全 None，给一个空 DataFrame
    return df if not df.empty else pd.DataFrame()