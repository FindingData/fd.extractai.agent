# fd.extractai.agent 实现要点（维护版）

## 1. 项目当前主线
- 当前可维护主线在 `packages/fd-extractai-report/src/fd_extractai_report`。
- 统一入口是 `ReportPipeline`：文档转换 -> 报告类型识别 -> 切片 -> 抽取 -> 校验/评估。
- `app/` 与部分 `tests/main_*.py` 更偏历史试验脚本，和主线能力有重复，不建议作为新功能入口。

## 2. 核心流程（建议以后都围绕这个扩展）
1. `load/load_bytes`：把 `doc/docx/pdf/...` 转成 Markdown，并写入 `ReportContext.markdown_text`。
2. `step_detect_report_type`：按关键词和加权规则识别 `house/land/asset`。
3. `step_slice`：根据报告类型绑定切片规则集，产出 `context.slices[key] -> List[ReportSection]`。
4. `step_extract`：按抽取规则集逐个 extractor 执行 LangExtract，得到结构化输出。
5. `validate/benchmark`：可选质量校验与基准评测。

## 3. 关键模块职责
- `pipeline.py`：总编排、阶段化执行、可分步运行、`run_until` 调试能力。
- `context.py`：运行上下文与切片存储模型，约定所有中间态结构。
- `converters/markdown_converter.py`：文档转 Markdown（`.doc` 依赖 LibreOffice/`soffice`）。
- `detectors/type_detector.py`：报告类型检测（强匹配 + 加权匹配 + 置信度降级默认）。
- `sections/rule_engine_slicer.py`：规则引擎切片器，支持多个模式（heading/regex/table/window/between/segment_tables）。
- `rules/slicing/*`：切片规则 schema、默认规则、registry、加载器。
- `extractors/base.py`：单 extractor 执行器（prompt + examples + OpenAI 兼容模型调用）。
- `extractors/rule_engine_extractor.py`：抽取器编排器，按规则集顺序执行。
- `rules/extracting/*`：抽取规则 schema、默认规则、registry、加载器。

## 4. 配置与运行时约定
- 包内配置：`fd_extractai_report/settings.py`，读取 `LLM_MODEL_ID/LLM_BASE_URL/LLM_API_KEY/LLM_TIMEOUT`。
- 根目录还有 `config.py`（历史脚本常用，字段与包内配置不完全一致）。
- 维护建议：新代码优先使用包内 `settings.py`，减少双配置源导致的漂移。

## 5. 规则系统设计（本项目的核心可扩展点）
- 切片规则：按 `report_type` 选择 `SliceRuleSet`，每个 `SliceStep` 定义 `mode/targets/within/params/missing`。
- 抽取规则：按 `report_type` 选择 `ExtractRuleSet`，每个 `ExtractorSpec` 定义 `prompt/input_slice_keys/examples/defaults`。
- 两类规则都支持 override + merge，能做灰度调整，不必改核心代码。

## 6. 输入输出契约
- 输入：文件路径或文件 bytes（推荐 bytes 模式用于服务端场景）。
- 中间态：`ReportContext`（markdown、slices、metadata）。
- 输出：`PipelineResult(outputs: Dict[str, List[dict]])`，按 extractor 的 `output_key` 分桶。

## 7. 后续开发建议（按优先级）
1. 统一入口：新功能都从 `ReportPipeline` 扩展，不再新增并行流程。
2. 统一配置：合并 `config.py` 与 `settings.py`，保留单一配置源。
3. 统一编码：当前部分文件存在中文乱码痕迹，建议统一 UTF-8 并清理历史注释。
4. 测试分层：将 `tests/main_*.py` 这类脚本与真正可执行测试分离（如 `tests/scripts/`）。
5. 规范输出：沉淀标准输出 JSON schema，避免下游字段漂移。

## 8. 新增一个报告类型的标准步骤
1. 在 `detectors/type_detector.py` 增加该类型识别规则（强特征 + hints/neg）。
2. 在 `rules/slicing/default_rulesets.py` 增加该类型切片规则。
3. 在 `rules/extracting/default_rulesets.py` 增加该类型抽取器定义。
4. 新增对应 prompt 和 examples。
5. 用 `run_until(..., until="slice"/"extract")` 先看切片，再看抽取结果。

## 9. 维护风险清单（当前代码现状）
- 存在历史脚本与主线并存，容易被误用为入口。
- 部分测试/脚本包含明显草稿或注释化代码，自动化测试可信度有限。
- 仓库包含 `__pycache__` 产物，可能干扰检索与评审。
- `.doc` 转换依赖系统安装 `soffice`，部署时需显式校验。
