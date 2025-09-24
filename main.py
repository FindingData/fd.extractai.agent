import sys,json
from app.processor_con import process_con_file
from app.processor_report import process_report
import asyncio  # 导入 asyncio 用于运行异步函数
from datetime import datetime
import os,pathlib
from pathlib import Path
from app.utils.text_utils import convert_docx_to_md
from app.utils.markdown_utils import sectionize,bucket_by_targets
from typing import Iterable, Sequence, Iterable, Any, Dict,List, Union,Tuple
from langextract import extract
from langextract.core import data
from dotenv import load_dotenv


EXPORT_DIR = Path(os.getcwd()) / "exports"

example_1 = data.ExampleData(
        text= """参加估价的注册房地产估价师
|  |  |  |  |
| --- | --- | --- | --- |
| 姓名 | 注册号 | 签名 | 签名日期 |
| 张未奋 | 4320200098 |  | 年 月 日 |
| 李萍 | 4320040057 |  | 年 月 日 |
""",
        extractions=[           
            data.Extraction("appraiser", "张未奋", attributes={ "appraiser":"张未奋", "register_id": "4320200098"}),
            data.Extraction("appraiser", "李萍", attributes={"appraiser":"李萍", "register_id": "4320040057"})            
        ],
    )


EXAMPLES: Sequence[data.ExampleData] = [example_1]
def _ensure_api_key() -> str:
    """Fetch the LangExtract API key or raise a helpful error."""
    load_dotenv()
    api_key = os.getenv("LANGEXTRACT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set the LANGEXTRACT_API_KEY environment variable before running the demo."
        )
    return api_key

def _as_dict(extraction: data.Extraction) -> dict[str, object]:
    """Convert an Extraction object into a JSON-serialisable dict."""
    char_interval = extraction.char_interval
    return {
        "class": extraction.extraction_class,
        "text": extraction.extraction_text,
        "attributes": extraction.attributes or {},
        "start": char_interval.start_pos if char_interval else None,
        "end": char_interval.end_pos if char_interval else None,
    }


def print_excel_requirements():
    """在输入 Excel 文件路径之前，给用户一个提示"""
    print("⚠️ 提示：程序需要处理的 Excel 文件必须包含以下两列：")
    print("1. '全文'：包含公告的全部文本内容")
    print("2. '当前网页URL'：包含每一条记录对应的网址链接")
    print("确保文件中这两列的名称完全匹配，否则程序无法正常工作。\n")

if __name__ == "__main__":
     file_path = sys.argv[1] if len(sys.argv) > 1 else input("请输入docx路径：")
     
    #  output_path = EXPORT_DIR / f'解析清单_{datetime.now().strftime("%Y%m%d_%H%M%S.md")}'
    #  result = convert_docx_to_md(file_path)
    #  pathlib.Path(output_path).write_text(result, encoding="utf-8")

     md_text = pathlib.Path(file_path).read_text(encoding="utf-8")

    # 你的同义词表（可放 YAML）
     config = {
        "valuation_purpose": ["注册房地产估价师"],
        #"valuation_object":  ["估价对象"],
        # "ownership_status":  ["权属情况","权证信息","产权信息"],
        # "valuation_basis":   ["估价依据","评估依据","法律法规与标准"],
        # "valuation_methods": ["估价方法","评估方法","方法选择"],
        # "market_analysis":   ["市场分析","区域与个案分析","市场背景"],
        # "valuation_date":    ["估价时点","评估时点","价值时点"],
        # "conclusions":       ["估价结论","评估结论","最终结论"],
        # "assumptions_risks": ["假设与限制","特殊假设","风险提示"],
     }

     secs = sectionize(md_text)
     buckets = bucket_by_targets(secs, config)

    # 例：拿“估价依据”
     vb = buckets.get("valuation_purpose", [])
     if vb:
        print("注册房地产估价师\n", vb[0]["content"], "...")
     text = vb[0]["content"]
     annotated_doc = extract(
        text,
        prompt_description="""从评估报告中提取以下结构化信息。提取的信息必须严格来自报告原文，不要进行概括或转述。""",
        examples=EXAMPLES,
        api_key=_ensure_api_key(),
        format_type=data.FormatType.JSON,
        max_char_buffer=400,
    )

     extractions: Iterable[data.Extraction] = annotated_doc.extractions or []
     print(
        json.dumps(
            [_as_dict(extraction) for extraction in extractions],
            indent=2,
            ensure_ascii=False,
        )
    )
    # print_excel_requirements()
    # file_path = sys.argv[1] if len(sys.argv) > 1 else input("请输入Excel路径：")
    # result = asyncio.run(process_con_file(file_path))
    # print(f"✅ 提取完成，共处理 {result['success_count']} 条，失败 {result['failed_count']} 条")
    # if result['failed']:
    #     print("❌ 以下条目处理失败：")
    #     for item in result['failed']:
    #         print(f"第 {item['index']} 条: {item['error']}")
    # print(f"全部处理处理完成")