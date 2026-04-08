# STATE.md

> 记录当前正在执行到哪里，以及下一步接什么。
> 只保留当前上下文，不记录阶段历史。

## 当前阶段
报告抽取分析（新功能）: checklist 链路已跑通，当前进入结果质量核查阶段

## 当前焦点
在 `zlqd` 批处理里稳定输出 checklist 的抽取、去重、分类结果，并检查分类命中质量是否符合预期。

## 当前断点
- `tests/test_checklist_pipeline.py` 已支持在 pipeline 调用前强制指定 `report_type="checklist"`，用于调试和批量验证 checklist 链路
- `rules/slicing/default_rulesets.py` 中 `ruleset_checklist` 已改为全文窗口切片：
  - `mode="by_window_after"`
  - `targets=[r"\S"]`
  - `window_chars=50000`
- `detectors/type_detector.py` 已补强 checklist 识别规则，能更优先识别“资料清单/商请提供资料/调取资料”等文档
- `analysis/checklist_analyzer.py` 已替换为本地确定性分析器，不再依赖原先会报 schema error 的分析逻辑
- 已执行：`python tests/test_checklist_pipeline.py`
- 本轮批处理结果：
  - `total=24`
  - `success=24`
  - `failed=0`
  - `raw_items_count=284`
  - `merged_analysis_count=247`
- 输出目录：`inputs/zlqd/_outputs/checklist_pipeline`

## 最近完成
- 修复 checklist 分析阶段为空的问题
- 恢复并验证 `analysis.json` 与 `analysis.md` 的生成
- 完成一轮 `zlqd` 全量批处理验证

## 下一步
1. 抽查 `inputs/zlqd/_outputs/checklist_pipeline` 中的 `analysis.json` / `analysis.md`，评估分类规则是否需要继续细化
2. 若要回归真实检测链路，移除测试中的强制 `checklist`，再验证 detector 是否已足够稳定
3. 如需更强归并效果，再补充别名归一化规则和分类关键词
