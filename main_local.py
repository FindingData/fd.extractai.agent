import sys,json
from app.processor_con import process_con_file
from app.processor_report import process_report
from app.processor import process_land_file
import asyncio  # 导入 asyncio 用于运行异步函数
from datetime import datetime
import os,pathlib
from pathlib import Path
from app.utils.text_utils import convert_docx_to_md
from app.utils.markdown_utils import sectionize,bucket_by_targets,extract_title_plus_pipe_table,extract_basic_info_table
from typing import Iterable, Sequence, Iterable, Any, Dict,List, Union,Tuple
import langextract as lx
from langextract.core import data
from dotenv import load_dotenv
from config import CONFIG
import dataclasses
 
EXPORT_DIR = Path(os.getcwd()) / "exports"
example_1 = data.ExampleData(
    text= """
    |  |  |  |
| --- | --- | --- |
| 估价报告编号： | 湘经典（2025）衡房011809A | |
| 估价项目名称： | 雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估 | |
| 估价委托人： | 长沙银行股份有限公司 | |
| 房地产估价机构： | 湖南经典房地产评估咨询有限公司 | |
| 注册房地产估价师： | 马庄 | 注册号：4320240054 |
|  | 李萍 | 注册号：4320040057 |
| 估价报告出具日期： | 2025年09月16日 | |
    """,
    extractions=[
         data.Extraction(
            "front_page_info",
            "湘经典（2025）衡房011809A", # 抽取报告编号作为锚点
            attributes={
                "report_no": "湘经典（2025）衡房011809A",
                "project_name": "雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估",
                "client_name": "长沙银行股份有限公司",
                "institution_name": "湖南经典房地产评估咨询有限公司",
                "appraiser_names": "马庄, 李萍", # 抽取为组合字符串
                "appraiser_reg_nos": "4320240054, 4320040057",
                "report_date": "2025年09月16日",
            }
        ),
    ]
)

def extraction_to_dict_fast(extraction: data.Extraction) -> dict:
    """
    将 Extraction 对象安全地转换为字典，处理非 JSON 序列化类型。
    """
    # 1. 首先转换为字典
    extraction_dict = dataclasses.asdict(extraction)

    # 2. 遍历并修正不可序列化的字段
    
    # 修正 'alignment_status' 字段
    alignment_status = extraction_dict.get('alignment_status')
    if alignment_status is not None:
        # 如果它是 Enum 或自定义对象，将其转换为字符串
        # 假设它是 Python Enum，使用 .name 或 .value 属性
        try:
            # 尝试使用 .name 属性，这是 Enum 转换为字符串的常见方法
            extraction_dict['alignment_status'] = alignment_status.name 
        except AttributeError:
            # 如果没有 .name 属性，则简单地调用 str()
            extraction_dict['alignment_status'] = str(alignment_status)

    # 3. 返回修正后的字典
    return extraction_dict

#EXAMPLES: Sequence[data.ExampleData] = [example_1, example_2, example_3, example_4, example_5, example_6]

EXAMPLES_SIM = [example_1]
if __name__ == "__main__":
     #file_path = sys.argv[1] if len(sys.argv) > 1 else input("请输入docx路径：")
     
     file_path = r"C:\code\fd\fd.extractai.agent\inputs\3_short.md"
     md_text = pathlib.Path(file_path).read_text(encoding="utf-8")

     prompt = """
        从评估报告中提取以下结构化信息： 
        1. 估价报告编号 
        2. 估价项目名称
        3. 估价委托人 
        4. 房地产估价机构 
        5. 注册房地产估价师姓名及注册号
        6. 估价报告出具日期
        所有提取信息必须严格来自报告原文，不要进行概括或转述。
    """
     text = md_text
     annotated_doc = lx.extract(
        text,
        prompt_description=prompt,
        examples=EXAMPLES_SIM,                
        model_id=CONFIG.LOCAL_MODEL_NAME,
        model_url=CONFIG.LOCAL_MODEL_URL,
        max_char_buffer=8192,
    )

     extractions: Iterable[data.Extraction] = annotated_doc.extractions or []
     if extractions:
        print("✅ 抽取结果:")
        print(
           json.dumps([extraction_to_dict_fast(e) for e in extractions], ensure_ascii=False, indent=2)
        )
     else:
        print("⚠️ 警告：LangExtract 未能提取到任何结构化信息。")
 