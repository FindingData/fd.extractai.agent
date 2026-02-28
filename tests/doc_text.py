from __future__ import annotations
import sys,os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # 添加项目根目录到sys.path
import json
import time
from pathlib import Path
from typing import Any, Dict, List,Optional
# 建议先用这个简单的脚本测试一下转换是否真正跑通
from markitdown import MarkItDown
import shutil



if __name__ == "__main__":
     # 再次确认
    print("soffice =", shutil.which("soffice"))
    print("libreoffice =", shutil.which("libreoffice"))
    md = MarkItDown()
    try:
        # 找一个具体的 .doc 文件路径试一下
        result = md.convert(r"C:\code\fd\fd.extractai.agent\inputs\report_detect\93832Z.doc") 
        print("🎉 转换成功！前 100 个字符如下：")
        print(result.text_content[:100])
    except Exception as e:
        print(f"❌ 依然转换失败: {e}")