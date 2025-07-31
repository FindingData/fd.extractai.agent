import sys
from app.processor import process_land_file
import asyncio  # 导入 asyncio 用于运行异步函数

def print_excel_requirements():
    """在输入 Excel 文件路径之前，给用户一个提示"""
    print("⚠️ 提示：程序需要处理的 Excel 文件必须包含以下两列：")
    print("1. '全文'：包含公告的全部文本内容")
    print("2. '当前网页URL'：包含每一条记录对应的网址链接")
    print("确保文件中这两列的名称完全匹配，否则程序无法正常工作。\n")

if __name__ == "__main__":
    print_excel_requirements()
    file_path = sys.argv[1] if len(sys.argv) > 1 else input("请输入Excel路径：")
    result = asyncio.run(process_land_file(file_path))
    print(f"✅ 提取完成，共处理 {result['success_count']} 条，失败 {result['failed_count']} 条")
    if result['failed']:
        print("❌ 以下条目处理失败：")
        for item in result['failed']:
            print(f"第 {item['index']} 条: {item['error']}")
    print(f"全部处理处理完成")