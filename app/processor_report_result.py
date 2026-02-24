"""Extract structured report details from DOCX files with LangExtract."""

from __future__ import annotations
import json
import logging
import os
import re
from dataclasses import dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence, Iterable, Any, Dict,List, Union,Tuple,Optional
import pandas as pd
import langextract as lx
from langextract.core import data
from app.utils.file_parser import EXPORT_DIR
from config import CONFIG
from langextract.providers.openai import OpenAILanguageModel

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

example_valuation_dispersed = data.ExampleData(
    text="""
    估价对象基本情况一览表
    | 名称 | 坐落 | 规划用途 | 权证号码 | 产权人 | 产权面积（㎡） |
    | --- | --- | --- | --- | --- | --- |
    | 保利天禧 | 岳麓区... | 办公 | 湘(2023)长沙市不动产权第0386909号 | 杨瑾 | 40.75 |
    
    估价结果汇总表
    | 项目及结果 | | 结果 |
    | --- | --- | --- |
    | 1.假定未设立法定优先受偿权下的价值 | 总价（元） | 313816 |
    """,
    extractions=[
        data.Extraction(
            "valuation_target_item",
            "湘(2023)长沙市不动产权第0386909号",
            attributes={
                "object_num": "估价对象1",
                "certificate_number": "湘(2023)长沙市不动产权第0386909号",
                "owner_name": "杨瑾",
                "building_area": 40.75,
                "usage": "办公",
                "total_price": 313816
            }
        )
    ]
)


qwen_model = OpenAILanguageModel(  
    model_id=CONFIG.QWEN_MODEL_NAME, 
    api_key = CONFIG.QWEN_KEY,
    base_url=CONFIG.QWEN_MODEL_URL,
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
    EXAMPLES: Sequence[data.ExampleData] = [example_valuation_result,example_valuation_dispersed]
    prompt = """
    你是一个专业的房地产估价数据提取助手。请从给定的 Markdown 文本中提取所有估价对象的信息。    
    ### 提取规则：
    1. **识别逻辑**：
       - 优先从“估价结果一览表”或“估价对象基本情况一览表”提取。
       - 如果“估价结果一览表”中只有面积和价格，请从上文的“致估价委托人函”或“基本情况表”中补全'权证号'和'产权人'。
    2. **属性定义**：
       - `certificate_number`: 权证号/不动产权证号。
       - `owner_name`: 权利人/产权人。
       - `building_area`: 建筑面积/产权面积，需提取纯数字。
       - `usage`: 房屋用途/规划用途。
       - `total_price`: 评估总价（通常取“抵押价值”或“假定未设立法定优先受偿权下的价值”）。
    3. **多条记录处理**：       
    - **合并策略**：若多行记录或多个权证号共享同一个“坐落”、“建筑面积”和“总价”，**必须**将其判定为同一个估价对象，合并输出。
    - **权证号处理**：若同一个对象对应多个权证号，请用“/”或“,”连接后填入 `certificate_number`，不要拆分成多条记录。
    - **产权人处理**：若有多个产权人，请全部保留并用空格分隔。
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


def quick_extract(
    text: str,
    max_char_buffer: int = 12000,
    num_ctx: int = 16384,
    timeout_seconds: int = 120,
) -> List[Dict[str, Any]]:
    """
    极简 LangExtract 封装：输入文本 + prompt (+ examples)，直接返回 attributes 列表。
    """
    if not text or not text.strip():
        return []
    EXAMPLES: Sequence[data.ExampleData] = [example_valuation_result,example_valuation_dispersed]
    prompt = """
    你是一个专业的房地产估价数据提取助手。请从给定的 Markdown 文本中提取所有估价对象的信息。    
    ### 提取规则：
    1. **识别逻辑**：
       - 优先从“估价结果一览表”或“估价对象基本情况一览表”提取。
       - 如果“估价结果一览表”中只有面积和价格，请从上文的“致估价委托人函”或“基本情况表”中补全'权证号'和'产权人'。
    2. **属性定义**：
       - `certificate_number`: 权证号/不动产权证号。
       - `owner_name`: 权利人/产权人。
       - `building_area`: 建筑面积/产权面积，需提取纯数字。
       - `usage`: 房屋用途/规划用途。
       - `total_price`: 评估总价（通常取“抵押价值”或“假定未设立法定优先受偿权下的价值”）。
    3. **多条记录处理**：       
    - **合并策略**：若多行记录或多个权证号共享同一个“坐落”、“建筑面积”和“总价”，**必须**将其判定为同一个估价对象，合并输出。
    - **权证号处理**：若同一个对象对应多个权证号，请用“/”或“,”连接后填入 `certificate_number`，不要拆分成多条记录。
    - **产权人处理**：若有多个产权人，请全部保留并用空格分隔。
     """
    
    annotated_doc = lx.extract(
        text,
        prompt_description=prompt,
        examples=EXAMPLES or [],       
        model=qwen_model,
        max_char_buffer=max_char_buffer,
        language_model_params={
            "num_ctx": num_ctx,
            "timeout": timeout_seconds,
        },
    )

    extractions = getattr(annotated_doc, "extractions", None) or []
    rows: List[Dict[str, Any]] = []
    for e in extractions:
        attrs = getattr(e, "attributes", None)
        if isinstance(attrs, dict) and attrs:
            rows.append(attrs)

    return rows

def _flatten_attributes(rows_attrs: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    """把多条 Extraction 的 attributes 动态铺平为列（不存在的键补 NaN）"""
    # 用 json_normalize 可以应对嵌套结构（如 dict/list）
    df = pd.json_normalize(list(rows_attrs), sep=".")
    # 若 attributes 为空列表/全 None，给一个空 DataFrame
    return df if not df.empty else pd.DataFrame()