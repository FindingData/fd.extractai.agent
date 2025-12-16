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
from langextract import extract
from langextract.core import data
from dotenv import load_dotenv
from config import CONFIG


EXPORT_DIR = Path(os.getcwd()) / "exports"

example_1 = data.ExampleData(
    text= """
    估价报告编号：湘经典（2025）衡房011809A
    估价项目名称：雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估
    估价委托人：长沙银行股份有限公司
    房地产估价机构：湖南经典房地产评估咨询有限公司
    注册房地产估价师：马庄，注册号：4320240054
    估价报告出具日期：2025年09月16日
    """,
    extractions=[           
        data.Extraction("valuation_report_number", "湘经典（2025）衡房011809A"),
        data.Extraction("valuation_project_name", "雁峰区和平南路9号（建筑面积为219.29平方米）房地产抵押价值评估"),
        data.Extraction("client_name", "长沙银行股份有限公司"),
        data.Extraction("valuation_institution", "湖南经典房地产评估咨询有限公司"),
        data.Extraction("appraiser_names", "马庄, 李萍"),
        data.Extraction("appraiser_registration_numbers", "4320240054, 4320040057"),
        data.Extraction("report_issue_date", "2025年09月16日"),
    ],
)

example_2 = data.ExampleData(
    text= """
    估价对象：雁峰区和平南路9号
    坐落：雁峰区和平南路9号
    建筑面积：219.29平方米
    层数：1/8
    规划用途：商服
    权证号码：衡房权证雁峰区字第00216768号/衡国用（2006B）第3051333号
    产权人：廖湖北
    产权面积：219.29平方米
    """,
    extractions=[           
        data.Extraction("property_name", "雁峰区和平南路9号"),
        data.Extraction("property_location", "雁峰区和平南路9号"),
        data.Extraction("building_area", "219.29平方米"),
        data.Extraction("floor_info", "1/8"),
        data.Extraction("planned_use", "商服"),
        data.Extraction("ownership_certificate_number", "衡房权证雁峰区字第00216768号/衡国用（2006B）第3051333号"),
        data.Extraction("owner_name", "廖湖北"),
        data.Extraction("property_area", "219.29平方米"),
    ],
)


example_3 = data.ExampleData(
    text= """
    假定未设立法定优先受偿权下的价值
    总价（元）：4408825元
    单价（元/m2）：20105元
    估价师知悉的法定优先受偿款
    总额（元）：0元
    已抵押担保的债权数额
    总额（元）：0元
    抵押价值
    总价（元）：4408825元
    单价（元/m2）：20105元
    """,
    extractions=[           
        data.Extraction("assumed_value", "4408825元"),
        data.Extraction("unit_price", "20105元/m2"),
        data.Extraction("known_priority_claims", "0元"),
        data.Extraction("mortgage_value", "4408825元"),
    ],
)

example_4 = data.ExampleData(
    text= """
    估价假设：本估价报告依据产权人提供的相关资料，产权人对资料的合法性、真实性、准确性和完整性负责。
    估价对象已设立抵押他项权利，房屋所有权人须注销估价对象原抵押他项权利，方能办理新的抵押贷款手续。
    本次评估不将原已抵押担保的债权数额计入优先受偿款。
    """,
    extractions=[           
        data.Extraction("valuation_assumptions", "产权人对资料的合法性、真实性、准确性和完整性负责"),
        data.Extraction("mortgage_registration", "房屋所有权人须注销估价对象原抵押他项权利，方能办理新的抵押贷款手续"),
        data.Extraction("priority_claim_exclusion", "本次评估不将原已抵押担保的债权数额计入优先受偿款"),
    ],
)

example_5 = data.ExampleData(
    text= """
    变现能力等级：二级
    预计可实现变现时间：6～12个月
    变现难易度：较好
    """,
    extractions=[           
        data.Extraction("liquidity_level", "二级"),
        data.Extraction("estimated_realization_time", "6～12个月"),
        data.Extraction("liquidity_difficulty", "较好"),
    ],
)

example_6 = data.ExampleData(
    text= """
    变现风险预计：估价对象所处区域环境较好，公用基础设施较齐全，交通便利度较高。
    市场风险：房地产市场波动较大，可能导致抵押房地产价值下跌。
    政策风险：政策变动可能对房地产市场产生较大影响。
    """,
    extractions=[           
        data.Extraction("realization_risk", "估价对象所处区域环境较好，公用基础设施较齐全，交通便利度较高"),
        data.Extraction("market_risk", "房地产市场波动较大，可能导致抵押房地产价值下跌"),
        data.Extraction("policy_risk", "政策变动可能对房地产市场产生较大影响"),
    ],
)




EXAMPLES: Sequence[data.ExampleData] = [example_1, example_2, example_3, example_4, example_5, example_6]
def _ensure_api_key() -> str:
    """Fetch the LangExtract API key or raise a helpful error."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
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
        "valuation_purpose": ["估价结果一览表"],
        #"valuation_object":  ["估价对象"],
        # "ownership_status":  ["权属情况","权证信息","产权信息"],
        # "valuation_basis":   ["估价依据","评估依据","法律法规与标准"],
        # "valuation_methods": ["估价方法","评估方法","方法选择"],
        # "market_analysis":   ["市场分析","区域与个案分析","市场背景"],
        # "valuation_date":    ["估价时点","评估时点","价值时点"],
        # "conclusions":       ["估价结论","评估结论","最终结论"],
        # "assumptions_risks": ["假设与限制","特殊假设","风险提示"],
     }
     
     pa = extract_title_plus_pipe_table(md_text, r"**估价对象基本情况一览表**")
     if pa:
        print("找到估价结果一览表段落：", pa)
     secs = sectionize(md_text)
     buckets = bucket_by_targets(secs, config)

    # 例：拿“估价依据”
     vb = buckets.get("valuation_purpose", [])
     if vb:
        print("注册房地产估价师\n", vb[0]["content"], "...")
     text = pa
     annotated_doc = extract(
        text,
        prompt_description="""从评估报告中提取以下结构化信息。提取的信息必须严格来自报告原文，不要进行概括或转述。""",
        examples=EXAMPLES,
        api_key=_ensure_api_key(),
        format_type=data.FormatType.JSON,
        max_char_buffer=400,
        model_id=CONFIG.LOCAL_MODEL_NAME,
        model_url=CONFIG.LOCAL_MODEL_URL,
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
    # result = asyncio.run(process_land_file(file_path))
    # print(f"✅ 提取完成，共处理 {result['success_count']} 条，失败 {result['failed_count']} 条")
    # if result['failed']:
    #     print("❌ 以下条目处理失败：")
    #     for item in result['failed']:
    #         print(f"第 {item['index']} 条: {item['error']}")
    # print(f"全部处理处理完成")