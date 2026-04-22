# Phase 2 - OCR 插件接入 Markdown 转换层

## Goal

- 在 `MarkdownFileConverter` 中可选启用 `markitdown-ocr`，让 `.doc/.docx/.pdf/.pptx/.xlsx` 中图片内文字可通过本地 OpenAI-compatible 视觉模型识别并并入 Markdown 输出。
- 保持默认行为兼容：未启用 OCR 时，现有转换链路与输出尽量不变。

## Background

- 当前转换层直接使用 `MarkItDown()`，对文档内图片文字没有额外识别能力。
- `runtime/ISSUES.md` 的 Ready 项明确要求接入 `markitdown-ocr`，并复用当前本地模型配置链路。
- 现有项目已经通过 `settings.LLMConfig.from_env()` 统一读取 `model_id`、`base_url`、`api_key`、`timeout`，OCR 接入应沿用同一配置入口，避免第二套配置源。

## Scope

- `packages/fd-extractai-report/pyproject.toml`
  - 补充 OCR 插件所需依赖声明。
- `packages/fd-extractai-report/src/fd_extractai_report/settings.py`
  - 增加 OCR 开关与 OCR 相关可选配置，统一由 `LLMConfig.from_env()` 读取。
- `packages/fd-extractai-report/src/fd_extractai_report/converters/markdown_converter.py`
  - 将 `MarkItDown()` 初始化改为可配置、可选启用 plugin 的构造流程。
  - 复用统一 LLM 配置构造 OpenAI-compatible client，供 `markitdown-ocr` 使用。
  - 明确插件缺失、OCR 启用但配置不完整、OCR 调用失败时的异常与回退策略。
- `tests/` 或 `tests/scripts/`
  - 增加面向转换层的 OCR 调试/验证脚本。

## Non-Goals

- 不修改 `app/` 历史目录。
- 不修改 slicer、extractor、analyzer 业务逻辑。
- 不引入新的生产入口，继续由 `ReportPipeline` 统一调用转换层。

## Design Notes

- 依赖侧
  - 声明 `markitdown-ocr`。
  - 明确声明 `openai` 依赖，用于构造兼容本地模型网关的 client。
- 配置侧
  - 默认 `ocr` 关闭，避免无模型环境下影响现有流程。
  - OCR 模型默认可回退到 `LLMConfig.model_id`；仅在需要差异化模型时再单独配置。
  - 若增加 OCR prompt，应作为可选配置项，而不是写死在代码中。
- 转换侧
  - `MarkdownFileConverter` 内部增加惰性构造逻辑，例如 `_build_markitdown()`、`_build_ocr_client()`。
  - `.doc` 仍先走 `soffice -> docx`，然后统一进入支持 OCR 的 MarkItDown 实例。
  - OCR 关闭时继续使用普通 `MarkItDown()`。
  - OCR 显式开启但插件不可用、client 构造失败或配置缺失时，应抛出明确异常；不要静默吞错。
- 日志侧
  - 新增日志统一使用 `logging`，不在主线包内增加 `print`。

## Execution Steps

1. 梳理 `markitdown-ocr` 接口
   - 确认 plugin 通过 `MarkItDown(enable_plugins=True, llm_client=..., llm_model=...)` 接入。
   - 明确其对 `openai` client 和 OpenAI-compatible 网关的兼容方式。
2. 设计配置收口
   - 在 `settings.LLMConfig` 中增加 OCR 开关与 OCR 可选参数。
   - 约定默认值与回退关系，确保旧调用方无感。
3. 重构转换器初始化
   - 为 `MarkdownFileConverter` 增加配置注入能力。
   - 根据配置决定构造普通 `MarkItDown` 还是启用 plugin 的实例。
   - 补充明确异常与回退边界。
4. 补充验证脚本
   - 新增一个仅验证转换层的 OCR 调试脚本，便于对含图片 Word 文档做 smoke test。
   - 保留一个 OCR 关闭场景，确认旧行为不退化。
5. 执行回归验证
   - 至少验证转换层输出。
   - 若修改 `settings.py`，按项目规则补跑完整 E2E：`python tests/main_pipeline.py`。

## Validation

- 功能验证
  - OCR 关闭：现有 `doc/docx/pdf` 转 Markdown 行为保持兼容。
  - OCR 开启：含图片文字的文档能在输出 Markdown 中看到新增识别文本。
- 异常验证
  - OCR 开启但插件未安装：抛出明确异常。
  - OCR 开启但 LLM 配置缺失：抛出明确异常。
  - OCR 调用失败：抛出明确异常，不静默降级。
- 集成验证
  - `ReportPipeline.load()`、`load_bytes()` 经转换层调用后无新增异常。
  - `python tests/main_pipeline.py` 可跑通。

## Risks

- 本地模型必须支持视觉输入；若仅支持文本，OCR 结果可能为空或失败。
- `markitdown-ocr` 会替换内建 PDF/DOCX/PPTX/XLSX converter，需确认在 OCR 关闭时不会意外改变现有输出。
- Windows 环境下 `.doc -> .docx` 仍依赖 `soffice`，OCR 接入不应影响既有转换路径。

## Acceptance

- 仓库依赖中已声明 OCR 所需包。
- 转换层可通过统一配置显式启用/关闭 OCR。
- OCR 开启时能复用当前本地模型网关配置，无硬编码模型名、URL、Key。
- 相关验证脚本和 E2E 验证通过。
- `runtime/STATE.md` 与 `runtime/ISSUES.md` 已同步更新。
