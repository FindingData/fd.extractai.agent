# llms/factory.py
from .qwen import QwenLLM
from .kimi import KimiLLM
from .base_llm import BaseLLM

class LLMFactory:
    @staticmethod
    def get_llm(model_type: str, temperature: float = 0.2) -> BaseLLM:
        """
        根据传入的模型类型返回对应的LLM实例
        """
        if model_type == "qwen":
            return QwenLLM(temperature)
        elif model_type == "kimi":
            return KimiLLM(temperature)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")
