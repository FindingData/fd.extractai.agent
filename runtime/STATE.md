# STATE.md

> 当前状态控制台。
> 只记录“现在正在做什么”，不记录历史阶段正文。

## Current Step

报告抽取分析（新功能）：`checklist` 链路已跑通，当前进入结果质量核查阶段。

## Active Plan

- 核查 `zlqd` 批处理输出中的抽取、去重、分类质量。
- 评估是否需要继续细化归并规则与分类关键词。

## Goal

- 在 `zlqd` 批处理中稳定输出 `checklist` 的抽取、去重、分类结果，并检查分类命中质量是否符合预期。

## Blockers

- OCR 链路已可用，但 `qwen2.5vl:7b` 在部分图片上的识别质量仍有噪声，后续可能需要调 prompt 或更换视觉模型。

## Current Breakpoint

- `tests/test_checklist_pipeline.py` 已支持在 pipeline 调用前强制指定 `report_type="checklist"`，用于调试和批量验证 `checklist` 链路。
- `rules/slicing/default_rulesets.py` 中 `ruleset_checklist` 已改为全文窗口切片：
  - `mode="by_window_after"`
  - `targets=[r"\S"]`
  - `window_chars=50000`
- `detectors/type_detector.py` 已补充 `checklist` 识别规则，能更优先识别“资料清单 / 商请提供资料 / 调取资料”等文档。
- `analysis/checklist_analyzer.py` 已替换为本地确定性分析器，不再依赖原先会报 `schema error` 的分析逻辑。
- OCR 接入已完成：
  - `settings.py` 新增 `LLM_ENABLE_OCR`、`LLM_OCR_MODEL_ID`、`LLM_OCR_BASE_URL`、`LLM_OCR_API_KEY`、`LLM_OCR_PROMPT` 配置读取。
  - `converters/markdown_converter.py` 支持按配置启用 `markitdown-ocr`，并在依赖缺失或配置缺失时抛出明确异常。
  - `pipeline.py` 默认会将同一份 `llm_config` 传给转换层。
  - 新增 `tests/scripts/debug_markdown_ocr.py` 用于调试 path / bytes 两种转换入口。
- OCR 真实联调结果：
  - `.env` 中的 `LLM_OCR_BASE_URL=http://192.168.10.250:11434/v1` 可达。
  - 远端模型列表包含 `qwen2.5vl:7b`。
  - `inputs/report_bak/1.docx` 开关前后输出一致，说明该样本的图片 OCR 增益不明显。
  - `inputs/report_bak/2.docx` 开启 OCR 后输出从 `51736` 增至 `53527` 字符，确实插入了 `*[Image OCR] ... [End OCR]*` 内容。
  - 新增内容中既有有效识别文本，也存在乱码、噪声和重复编号，当前更像“功能已通、质量待调优”。
- `tests/scripts/debug_jd_extract.py` 已简化为“直接抽取文字”的调试脚本：
  - 默认输入 `inputs/jd/t_1.docx`。
  - 默认输出目录 `inputs/jd/_outputs/t_1_text`。
  - 不再走 pipeline / detect / slice / extract，仅调用 `MarkdownFileConverter` 输出 markdown 文本。
  - 支持 `--bytes`、`--enable-ocr`、`--disable-ocr`。
- 已执行验证：
  - `python -m py_compile packages/fd-extractai-report/src/fd_extractai_report/settings.py packages/fd-extractai-report/src/fd_extractai_report/converters/markdown_converter.py packages/fd-extractai-report/src/fd_extractai_report/pipeline.py tests/scripts/debug_markdown_ocr.py tests/scripts/debug_jd_extract.py`
  - `python tests/scripts/debug_markdown_ocr.py inputs/report_bak/1.docx --disable-ocr --output build/debug_markdown_ocr_noocr.md`
  - `python tests/scripts/debug_markdown_ocr.py README.md --enable-ocr --output build/debug_markdown_ocr_enabled.md`
  - `python tests/main_pipeline.py`
  - 直接验证 `ReportPipeline.load()` / `load_bytes()` 均能正常完成 `.docx -> markdown`
  - 探活 `http://192.168.10.250:11434/v1/models` 与 `http://192.168.10.250:11434/api/tags`
  - 对 `inputs/report_bak/2.docx` 进行 OCR 开关对比验证
  - `python tests/scripts/debug_jd_extract.py`
- 已发现的现存问题：
  - `python tests/test_report_detect_type.py` 仍会因脚本传入不存在的 `extractors` 参数而失败，属于仓库既有问题，非本轮 OCR 改动引入。

## Recently Done

- 修复 `checklist` 分析阶段为空的问题。
- 恢复并验证 `analysis.json` 与 `analysis.md` 的生成。
- 完成一轮 `zlqd` 全量批处理验证。
- 手工整理 `inputs/zlzl/analysis.md`，合并明显重复的标准名称。
- 已从 `inputs/zlzl/analysis.md` 导出 `inputs/zlzl/analysis.docx`。
- 完成转换层 OCR 插件接入、基础验证与真实视觉模型 smoke test。
- 将 `tests/scripts/debug_jd_extract.py` 简化为直接文字抽取脚本。

## Next Steps

1. 结合 `inputs/report_bak/2.docx` 的新增 OCR 片段，调优 `LLM_OCR_PROMPT` 或切换更强视觉模型，降低乱码与重复输出。
2. 如需提升 `jd/t_1.docx` 的识别稳定性，可针对土地证类图片单独优化 OCR prompt。
3. 抽查 `inputs/zlqd/_outputs/checklist_pipeline` 中的 `analysis.json` / `analysis.md`，评估分类规则是否需要继续细化。
