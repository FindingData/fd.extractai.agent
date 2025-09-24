from app.schemas.LandInfo import LandInfo
from app.schemas.HouseInfo import HouseInfo
from app.llm.factory import LLMFactory
from langchain.prompts import ChatPromptTemplate
from app.utils.prompt_utils import load_prompt
from app.utils.file_parser import load_excel,export_to_excel
from app.utils.async_utils import safe_async_chain
from datetime import datetime
import asyncio
import logging
#logging.basicConfig(level=logging.INFO)

async def process_con_file(file_path: str) -> dict:
    prompt_str = load_prompt("gen_con_data.txt")
    mainLLM =  LLMFactory.get_llm("qwen")
    backupLLM = LLMFactory.get_llm("kimi")
    prompt = ChatPromptTemplate.from_template(prompt_str)
    chain = prompt | mainLLM.llm
    backUpChain = prompt | backupLLM.llm
    columns_to_load = ["详细地址"]  # 你可以动态指定想要加载的列    
    text_list = load_excel(file_path, columns_to_load)
    results = []
    failed_items = []
    print(f"模型处理开始..")
    for i, row in enumerate(text_list.itertuples(), start=1):
        house_info = None  # 初始化 land_info 变量，用于存储结果        
        text = row.详细地址  # 获取"全文"列的内容
        try:
            result = await safe_async_chain(chain, {"raw_text": text}, timeout=20)
            print(f"押品原始地址:{text}")
            house_info = HouseInfo.from_content(result.content)  
            house_info.详细地址 = text
            print(f"✅ 第{i}条主模型成功处理.")             
            print(f"标准化后地址:{house_info}")                   
        except Exception as e:
            print(f"💥 第{i}条主模型失败: {e}")
            try:
                result = await safe_async_chain(backUpChain, {"raw_text": text}, timeout=20)
                house_info = HouseInfo.from_content(result.content)                                   
                print(f"✅ 第{i}条由Kimi成功处理.")
            except Exception as e2:
                print(f"❌ 第{i}条备用模型Kimi也失败: {e2}")
                failed_items.append({"index": i, "text": text, "error": str(e2)})
        if house_info:
              results.append(house_info)  
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S.xlsx")
    export_to_excel(results, f"解析清单_{timestamp}")
    return {"status": "complete", "success_count": len(results), "failed_count": len(failed_items), "data": [r.dict() for r in results], "failed": failed_items}
