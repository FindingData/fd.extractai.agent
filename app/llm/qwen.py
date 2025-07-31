# llms/qwen.py
from langchain_ollama import ChatOllama
from config import CONFIG
from .base_llm import BaseLLM

class QwenLLM(BaseLLM):
    def __init__(self, temperature: float = 0.2,top_p:float=0.9,num_ctx:int=4096):
        self.temperature = temperature
        self.llm = ChatOllama(
            base_url=f"{CONFIG.LOCAL_MODEL_URL}",
            model=CONFIG.LOCAL_MODEL_NAME,
            temperature=self.temperature,
            top_p=top_p,
            num_ctx=num_ctx
        )

    def generate_text(self, prompt: str) -> str:
        # 调用Qwen模型进行文本生成
        return self.llm.generate([prompt])    
    def close(self):
        """显式释放模型资源"""
        try:
            if hasattr(self.llm, 'close'):
                self.llm.close()  # 假设 `ChatOllama` 提供了一个 `close` 方法来清理资源
                print("模型资源已释放。")
        except Exception as e:
            print(f"释放模型资源时出错: {e}")

    def __del__(self):
        """析构函数，在销毁实例时自动调用，确保资源被清理"""
        self.close()