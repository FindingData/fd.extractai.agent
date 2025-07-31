from pydantic import BaseModel,Field
from typing import Optional,Union
from app.utils.text_utils import extract_clean_json
import json


class LandInfo(BaseModel):
    网址:str = ""
    宗地编号: str
    宗地总面积: str = Field(None, description="单位平方米")
    宗地坐落: str = ""
    使用年限: str = Field(None, description="单位年")
    容积率: str = ""
    建筑密度: str = ""
    绿化率: str = ""
    建筑限高: str = ""
    土地用途: str = ""
    起始价: str = Field(None, description="万元")
    竞买保证金: str = Field(None, description="万元")
    加价幅度: str = Field(None, description="万元")
    估价报告备案号: str = ""
    @staticmethod
    def from_content(content: str) -> Union['LandInfo', None]:
        try:
            # 直接进行解析
            result = LandInfo(**json.loads(extract_clean_json(content)))
            return result
        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            return None