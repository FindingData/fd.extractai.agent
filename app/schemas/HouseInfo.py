from pydantic import BaseModel, Field
from typing import Optional,Union
from app.utils.text_utils import extract_clean_json
import json

class HouseInfo(BaseModel):
    详细地址: str = ""
    城市名称: str = ""
    区域名称: str = ""
    宗地坐落: str = ""
    楼盘名称: str = Field(..., alias="楼盘名称")
    楼栋名称: str = ""
    房号名称: str = ""

    @staticmethod
    def from_content(content: str) -> Union['HouseInfo', None]:
        try:
            # 直接进行解析
            result = HouseInfo(**json.loads(extract_clean_json(content)))
            return result
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            return None
