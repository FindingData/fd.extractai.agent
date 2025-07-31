# llms/kimi.py
from langchain_openai import ChatOpenAI
from config import CONFIG
from .base_llm import BaseLLM

class KimiLLM(BaseLLM):
    def __init__(self, temperature: float = 0.2):
        self.temperature = temperature
        self.llm = ChatOpenAI(
            model_name=CONFIG.KIMI_MODEL_NAME,
            openai_api_base=CONFIG.KIMI_MODEL_URL,
            openai_api_key=CONFIG.KIMI_MODEL_KEY,
        )

    def generate_text(self, prompt: str) -> str:
        # 调用Kimi模型进行文本生成
        return self.llm.generate([prompt])
