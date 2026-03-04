
from markitdown import MarkItDown
import os,pathlib
import re
from pathlib import Path
import json
import pandas as pd
from app.processor_report import extract_valuation_data,quick_extract

# 1. 纯粹的文档转换方法
def batch_convert_docx_to_md(input_dir: str):
    """
    使用 MarkItDown 将指定目录下的 docx 文件批量转换为 md 文件
    """
    # 1. 初始化 MarkItDown 实例
    md = MarkItDown()
    
    input_path = Path(input_dir)
    # 如果没指定输出目录，则默认在输入目录下创建 'markdown_files' 文件夹
    # 2. 获取所有 docx 文件
    docx_files = list(input_path.glob("*.docx"))
    print(f"📂 发现 {len(docx_files)} 个待转换的文档...")
    
    results = []

    # 3. 执行转换
    for docx_file in docx_files:
        try:
            print(f"⏳ 正在转换: {docx_file.name} ...", end="", flush=True)
            
            # 核心转换代码
            result = md.convert(str(docx_file))
            
            # 生成目标文件名
            md_filename = docx_file.stem + ".md"
            md_file_path = input_path / md_filename
            
            # 写入文件
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
            
            print(f" ✅ 完成")
            results.append(md_file_path)
            
        except Exception as e:
            print(f" ❌ 失败: {str(e)}")
            
    print(f"\n✨ 批量转换完成！共成功转换 {len(results)} 个文件。")
    print(f"📁 结果保存在: {input_path}")
    return results

# 2. 纯粹的内容提取方法
def extract_short_sections(input_dir: Path):
    """
    遍历目录，将全量 md 文件切片为 _short.md
    """
    md_files = [f for f in input_dir.glob("*.md") if "_short" not in f.name]
    
    print(f"\n--- 阶段 2: 开始提取‘致函’片段 ({len(md_files)}个文件) ---")
    start_pattern = r"致\s*估\s*价\s*委\s*托\s*人\s*函[：:]?"
    end_pattern = r"目\s*录"
    # 定义匹配规则
    pattern = re.compile(f"({start_pattern}.*?)(?={end_pattern})", re.DOTALL | re.IGNORECASE)
    
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        match = pattern.search(content)
        
        if match:
            # 重新组合内容，保留标题作为上下文
            short_content = "致估价委托人函" + match.group(1).strip()
            short_path = input_dir / f"{md_file.stem}_short.md"
            short_path.write_text(short_content, encoding="utf-8")
            print(f"✂️  已切片: {short_path.name}")
        else:
            print(f"⚠️  未找到锚点: {md_file.name}")

# 3.基础测试预抽取
def generate_initial_benchmark(input_dir: Path,benchmark_file:str ='benchmark.json'):
    """
    读取所有 _short.md，利用 AI 自动生成一个初步的基准文件供人工校对
    """
    short_files = list(input_dir.glob("*_short.md"))
    initial_data = {}

    print(f"🚀 开始生成初版 Benchmark，共 {len(short_files)} 个文件...")

    for md_file in short_files:
        print(f"🧐 正在预抽: {md_file.name}...")
        content = md_file.read_text(encoding="utf-8")
        
        # 调用你的 LangExtract 抽取逻辑
        # 注意：这里使用的应该是你之前调试好的 schema 和 prompt
        try:
            
            initial_data[md_file.stem] = quick_extract(content)
            
        except Exception as e:
            print(f"❌ {md_file.name} 预抽失败: {e}")
            initial_data[md_file.stem] = []

    # 写入 JSON
    with open(input_dir / benchmark_file, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 初版 Benchmark 已生成: {input_dir}")
    print("👉 请现在打开该文件，根据原文核对并修正数据。修正完成后，它就是你的‘标准答案’了。")

current_file = Path(__file__).resolve()
# --- 执行转换 ---
if __name__ == "__main__":
    # 根据您的目录结构设置路径    
    app_root = current_file.parent
    input_directory = app_root / "inputs/report_hf"
    print(f"📂 正在扫描目录: {input_directory}")
    # 第一步：转换
    batch_convert_docx_to_md(input_directory)
    # 第二步：切片
    extract_short_sections(input_directory)
    # 第三步: 基准预抽
    generate_initial_benchmark(input_directory)