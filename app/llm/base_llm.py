# llms/base_llm.py
from app.utils.async_utils import safe_async_chain

class BaseLLM:
    def generate_text(self, prompt: str) -> str:
        """
        生成文本的方法，所有LLM都需要实现这个方法
        """
        raise NotImplementedError("This method should be overridden in subclasses")
    
    async def process_with_timeout(self, chain, inputs):
        result = await safe_async_chain(chain, inputs)
        return result