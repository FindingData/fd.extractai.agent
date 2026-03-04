import os
import re
import json
from pathlib import Path
from markitdown import MarkItDown
# 假设你的抽取逻辑在这个路径
from app.processor_report import extract_valuation_data

 
def generate_initial_benchmark(input_file: Path):
    """
    读取所有 _short.md，利用 AI 自动生成一个初步的基准文件供人工校对
    """     
    if not input_file.exists():
        print(f"❌ 错误：找不到文件 {input_file}")
        return
    # 1. 自动生成输出路径：同目录下，后缀改为 .json
    output_file = input_file.with_suffix('.json')
    initial_data = {}

    print(f"🚀 开始单文件预抽: {input_file.name}...")

    try:
        # 2. 读取内容
        content = input_file.read_text(encoding="utf-8")

        # 3. 调用 AI 抽取逻辑
        # 结果存入字典，key 使用文件名 stem（如 "1_short"）
        extracted_res = extract_valuation_data(content)
        initial_data[input_file.stem] = extracted_res

        # 4. 写入 JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 抽取完成！结果已保存至: {output_file.name}")

    except Exception as e:
        print(f"❌ {input_file.name} 预抽失败: {str(e)}")
        # 失败时也生成一个空结构，方便人工补全
        initial_data[input_file.stem] = []
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)

current_file = Path(__file__).resolve()

# --- 使用示例 ---
if __name__ == "__main__":
    app_root = current_file.parent
    input_directory = app_root / "inputs/report"
    input_file = input_directory / "2_short.md"
    # 第一步：转换
    #batch_convert_docx_to_md(input_directory)
    # 第二步：切片
    #extract_short_sections(input_directory)
    # 第三步: 基准预抽
    generate_initial_benchmark(input_file)