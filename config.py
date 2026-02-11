import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    LOCAL_MODEL_NAME = os.getenv('LOCAL_MODEL_NAME', 'qwen3:8b')
    LOCAL_MODEL_URL = os.getenv('LOCAL_MODEL_URL', 'http://220.168.40.130:5269')
    KIMI_MODEL_NAME = os.getenv('KIMI_MODEL_NAME', 'kimi-k2-0711-preview')
    KIMI_MODEL_URL = os.getenv('KIMI_MODEL_URL', 'https://api.moonshot.cn/v1')
    KIMI_MODEL_KEY = os.getenv('KIMI_MODEL_KEY')    
    
    QWEN_MODEL_URL  = os.getenv("QWEN_MODEL_URL",  "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME", "qwen-plus")
    QWEN_KEY        = os.getenv("QWEN_KEY",        "")

    MAX_TIMEOUT = int(os.getenv('MAX_TIMEOUT', 20))
    



# 实例化配置
CONFIG = Config()