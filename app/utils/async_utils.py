# utils/async_utils.py
import asyncio
from langchain_core.runnables import Runnable

async def safe_async_chain(chain: Runnable, inputs: dict, timeout: float = 20.0):
    """
    安全执行异步链式调用，处理超时和异常。
    :param chain: 链式任务
    :param inputs: 输入参数
    :param timeout: 超时设置
    :return: 返回链式任务的执行结果或 None
    """
    try:
        return await asyncio.wait_for(chain.ainvoke(inputs), timeout=timeout)
    except asyncio.TimeoutError:
        print(f"⏰ 推理超时，超过 {timeout} 秒")
        return None
    except Exception as e:
        print(f"💥 推理异常: {e}")
        return None
