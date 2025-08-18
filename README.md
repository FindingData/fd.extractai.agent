# fd.extractai.agent

基于 **Python + LLM** 的智能信息抽取代理，用于从不规则爬虫数据中提取有用信息，辅助后续数据清洗与分析。

## 🔧 技术栈
- Python 3.11+
- LangChain / LangGraph
- 本地/远程大语言模型 (LLM)
- Pandas / OpenPyXL / Numpy (用于数据处理)

## 🎯 功能目标
- 从结构化与非结构化的爬虫原始数据中抽取关键信息  
- 通过 LLM 对原始文本进行理解、解析与标准化  
- 输出 JSON/结构化数据，便于后续分析与入库  
