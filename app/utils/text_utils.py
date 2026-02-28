
import re
from typing import List,Union
from markitdown import MarkItDown
import shutil
import subprocess
from pathlib import Path
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
 
def convert_word_to_md(input_path: str | Path) -> str:
    path_obj = Path(input_path).resolve()
    suffix = path_obj.suffix.lower()
    
    # 强制检查：如果是 .doc 但没装 LibreOffice，直接报错给出清晰提示
    if suffix == ".doc":
        if not (shutil.which("soffice") or shutil.which("libreoffice")):
            raise RuntimeError("系统缺失 LibreOffice，无法处理 .doc 文件。请安装并配置 PATH。")

    md = MarkItDown()

    try:
        # 情况 A: .docx 格式，直接走原生高性能转换
        if suffix == ".docx":
            return md.convert(str(path_obj)).text_content

        # 情况 B: .doc 格式，手动触发标准化，防止 MarkItDown 内部识别失败
        if suffix == ".doc":
            # 1. 构造一个临时目标路径 (例如 test.doc -> test_auto.docx)
            temp_docx = path_obj.with_suffix(".__temp__.docx")
            
            # 2. 调用 LibreOffice (模拟 PR #36 的底层行为，但更可控)
            # 使用 headless 模式静默转换
            cmd = [
                "soffice",
                "--headless",
                "--convert-to", "docx",
                "--outdir", str(path_obj.parent),
                str(path_obj)
            ]
            
            # 执行转换
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)
            
            # LibreOffice 默认生成的名称是原名.docx，我们定位它
            generated_file = path_obj.with_suffix(".docx")
            
            if generated_file.exists():
                # 3. 将转换后的 docx 交给 MarkItDown 处理
                md_content = md.convert(str(generated_file)).text_content
                
                # 4. 清理：删除 LibreOffice 产生的临时 docx
                generated_file.unlink()
                return md_content
            else:
                raise FileNotFoundError(f"LibreOffice 未能生成目标文件: {result.stderr}")

    except Exception as e:
        # 捕获所有异常并包装，方便 Pipeline 调试
        raise RuntimeError(f"Word 转换失败 [{suffix}]: {str(e)}")

    # 兜底：如果是其他格式，直接尝试
    return md.convert(str(path_obj)).text_content


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
