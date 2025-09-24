
import re
from typing import List
from markitdown import MarkItDown

def extract_user_prompt(text):
    # 如果有 <think>...</think>，去掉它和中间内容，只取后面有效部分
    pattern = r'<think>.*?</think>\s*'
    cleaned = re.sub(pattern, '', text, flags=re.DOTALL)
    # 再去掉多余的空行
    return cleaned.strip()

def convert_docx_to_md(input_path: str) -> str:
    md = MarkItDown()  # 需要更强功能可传入 llm_client/docintel_endpoint 等
    result = md.convert(input_path)  # 支持文件路径/URL/字节流

    text = result.text_content
    return text
   

def extract_clean_json(text: str) -> str:
    # 1. 清除 <think>...</think> 块
    cleaned = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
    # 2. 清除 markdown 的 ```json 包裹（注意这里是真实换行符，不是\\n）
    cleaned = re.sub(r'^```json\s*', '', cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned.strip())
    return cleaned.strip()


def split_by_tokens(text: str, max_tokens: int = 2000) -> List[str]:
    """
    粗略按 token 长度估算将文本分段（中文 1 字 ≈ 1 token，英文词 ≈ 1-2 token）
    :param text: 原始文本
    :param max_tokens: 每段最大长度（默认2000 token）
    :return: 文本段落列表
    """
    # 先按自然段落（标点或换行）粗切
    # 中文句号、分号、换行、英文句号
    sentences = re.split(r'(?<=[。；;\\.!?？])|\\n', text)

    chunks = []
    current_chunk = ""
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # 粗略估算：1汉字=1 token，1英文单词≈1.3 token
        sentence_length = len(sentence)

        if current_length + sentence_length > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
            current_length = sentence_length
        else:
            current_chunk += sentence
            current_length += sentence_length

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
