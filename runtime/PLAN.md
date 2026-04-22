# PLAN.md — 项目开发计划

> 本文件记录项目长期计划、当前能力覆盖与功能路线图。
> 当前活跃执行计划见 `runtime/plans/_INDEX.md`，当前运行断点见 `runtime/STATE.md`。

更新时间：2026-04-08

---

## 当前执行阶段
报告抽取分析（新功能）

### 已完成功能
| 功能模块 | 状态 | 说明 |
|----------|------|------|
| DOC/DOCX/PDF → Markdown 转换 | ✅ 完成 | `converters/markdown_converter.py`，`.doc` 依赖 LibreOffice |
| 报告类型检测（house/land/asset） | ✅ 完成 | `detectors/type_detector.py`，强特征 + 加权关键词 + 置信度 |
| 规则引擎切片器 | ✅ 完成 | `sections/rule_engine_slicer.py`，支持 6 种切片模式 |
| house 类型切片规则 | ✅ 完成 | `rules/slicing/default_rulesets.py` |
| land 类型切片规则 | ✅ 完成 | `rules/slicing/default_rulesets.py` |
| asset 类型切片规则 | ✅ 完成 | `rules/slicing/default_rulesets.py` |
| house 类型抽取器 | ✅ 完成 | `rules/extracting/default_rulesets.py` + prompts |
| land 类型抽取器 | ✅ 完成 | `rules/extracting/default_rulesets.py` + prompts |
| asset 类型抽取器 | ✅ 完成 | `rules/extracting/default_rulesets.py` + prompts |
| Pipeline 总编排 | ✅ 完成 | `pipeline.py`，支持 `run_until` 分步调试 |
| 基准评测系统（benchmark） | ✅ 完成 | `benchmarks/`，结果写入 `benchmark.json` |
| 多 LLM 提供商支持 | ✅ 完成 | Kimi、Qwen、Doubao、本地 Ollama |
| 历史单文档处理脚本 | ✅ 完成（仅参考） | `app/processor_report.py`，不再维护 |
| 批量多线程 Pipeline | ✅ 完成 | `tests/main_pipeline_multi.py` |

### 各报告类型支持详情
| 报告类型 | 检测 | 切片 | 抽取 | 测试数据集 |
|----------|------|------|------|------------|
| `house`（房地产抵押估价） | ✅ | ✅ | ✅ | `inputs/report_bak/`, `report_bh/`, `report_hf/`, `report_cs/`, `report_zx/` |
| `land`（土地使用权出让） | ✅ | ✅ | ✅ | `inputs/td/` |
| `asset`（资产评估） | ✅ | ✅ | ✅ | `inputs/zc/` |

---

## 报告抽取分析（新功能）
在现有 ExtractAI 能力基础上，新增：
1. 配置一个新的报告类型（资料调取清单），并实现其抽取分析能力
2. 抽取输入报告中清单资料的条目
3. 将抽取结果输出为结构化 Markdown
4. 将所有抽取的结果汇总后，使用 LLM 实现一个简单的去重分类分析功能

---

## 功能路线图

### 近期（1-2 个月）

| 目标 | 说明 |
|------|------|
| 新报告类型：司法拍卖评估 | 检测规则 + 切片规则 + 抽取器 + prompt |
| 新报告类型：抵押物评估（扩展） | 对现有 house 类型的细分分支 |
| 输出 schema 标准化 | Pydantic 模型 + 下游入库字段对齐 |

### 中期（3-6 个月）

| 目标 | 说明 |
|------|------|
| HTTP API 服务化 | FastAPI 封装，支持文件上传与异步任务 |
| 批量处理优化 | 异步并发 Pipeline，提升吞吐量 |
| 本地模型质量提升 | 收集更多 few-shot examples，优化 prompts |
| 输出入库 | 对接 SQLite / PostgreSQL，标准化入库流程 |

### 长期

| 目标 | 说明 |
|------|------|
| 自动规则调优 | 基于 benchmark 结果自动调整切片/抽取规则权重 |
| 多语言报告支持 | 扩展至英文/繁中评估报告 |
| 前端可视化 | 抽取结果对比查看、人工审核修正界面 |

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [../AGENTS.md](../AGENTS.md) | AI 编码助手指导文档（项目约定、扩展方式） |
| [./STATE.md](./STATE.md) | 当前运行断点与下一步动作 |
| [./ISSUES.md](./ISSUES.md) | 运行期问题收集与分流入口 |
| [./plans/_INDEX.md](./plans/_INDEX.md) | 当前活跃 phase 与阶段计划索引 |
| [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) | 实现要点（历史维护笔记） |
| [../README.md](../README.md) | 项目概述与技术栈 |
