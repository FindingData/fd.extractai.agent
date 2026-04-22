# ISSUES.md

> Local intake buffer only.
> Small bugs and features: write here first, then run `fx issue create` to push to GitHub.
> `[Phase x.x]` is optional and only used for larger module-level work.
> Root-level `ISSUES.md` 已并入此文件，当前以 `runtime/ISSUES.md` 为准。

## Current Items

### Ready
- [quality] OCR 真实联调已跑通，但 `qwen2.5vl:7b` 在 `inputs/report_bak/2.docx` 的部分现场照片/证照图片上仍存在乱码、噪声和重复编号现象，后续可继续通过 `LLM_OCR_PROMPT` 或更强视觉模型优化质量。

### Resolved
- [feature] [Phase 2] 已完成 `markitdown-ocr` 接入：转换层支持通过 `LLMConfig.from_env()` 可选启用 OCR，复用 OpenAI-compatible 本地模型配置，并补充 `tests/scripts/debug_markdown_ocr.py` 调试脚本。
- [verify] 已完成真实 OCR smoke test：远端模型网关 `http://192.168.10.250:11434/v1` 可达，且存在 `qwen2.5vl:7b`；在 `inputs/report_bak/2.docx` 上，OCR 开启后输出由 `51736` 增至 `53527` 字符，并出现 `*[Image OCR] ... [End OCR]*` 新增片段。

### Deferred
- 无
