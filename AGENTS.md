# AGENTS.md
> 记录项目长期稳定的目标、架构原则与执行规则。
> 不记录阶段进度、已完成事项或临时断点。
> 执行时必须结合 `PLAN.md`、`ISSUES.md`、`STATE.md` 一起使用。

---

## 0. 启动任何任务前的强制检查顺序

在执行任何开发任务之前，必须按顺序完成以下检查：

1. 读取 `PLAN.md` → 确认当前任务属于哪个优先级条目
2. 读取 `STATE.md` → 确认当前进度断点，避免重复劳动
3. 读取 `ISSUES.md` → 确认任务是否存在已知阻塞或依赖
4. 读取目标模块的现有代码 → **严禁在未读代码的情况下直接修改**
5. 确认修改范围仅限 `packages/fd-extractai-report/src/fd_extractai_report/`

---

## 1. 代码写在哪里（硬性规则）

| 任务类型 | 必须写在 | 禁止写在 |
|----------|----------|----------|
| 新功能、新报告类型、新 extractor | `packages/fd-extractai-report/src/fd_extractai_report/` | `app/` |
| 切片 / 抽取规则 | `rules/slicing/` 或 `rules/extracting/` | pipeline.py 内硬编码 |
| Prompt 模板 | `fd_extractai_report/prompts/*.txt` | 代码字符串内嵌 |
| LLM 配置读取 | `settings.py` (`LLMConfig.from_env()`) | `config.py`、环境变量硬编码 |
| E2E / 调试脚本 | `tests/` | 主线包内 |
| 可执行脚本（非 pytest） | `tests/scripts/` | `tests/` 根目录 |

> `app/` 为历史只读目录。可以读取参考，**绝对禁止修改或在此新增任何代码**。

---

## 2. 任务执行决策树

### 新增报告类型（如司法拍卖、抵押物评估）

必须按以下顺序执行，**不允许跳步或乱序**：

```
Step 1  detectors/type_detector.py
        → 在 STRONG_PATTERNS / HINTS / NEG_PATTERNS 中添加识别规则

Step 2  rules/slicing/default_rulesets.py
        → 新增该类型的 SliceRuleSet（含所有 SliceStep）

Step 3  rules/slicing/registry.py
        → 注册 report_type → SliceRuleSet 的映射

Step 4  rules/extracting/default_rulesets.py
        → 新增 ExtractRuleSet（含 ExtractorSpec 列表）

Step 5  rules/extracting/registry.py
        → 注册 report_type → ExtractRuleSet 的映射

Step 6  fd_extractai_report/prompts/<type>_<field>.txt
        → 新增 prompt 模板文件

Step 7  验证（必做）
        → run_until(ctx, until="slice")  确认切片正确
        → run_until(ctx, until="extract") 确认抽取输出

Step 8  tests/
        → 补充对应测试用例或调试脚本
```

### 修改现有 extractor

1. 先读 `extractors/base.py` 了解基类接口
2. 只修改 `ExtractorSpec`（prompt / examples / input_slice_keys）
3. 不允许在 extractor 内部直接构造 LLM 实例
4. 修改后必须跑 `tests/test_report_extract.py` 验证结果无退化

### 修改切片规则

1. 先读 `sections/rule_engine_slicer.py` 确认 mode 参数含义（6 种：heading/regex/table/window/between/segment_tables）
2. 只修改 `rules/slicing/default_rulesets.py` 中的规则，不动切片引擎本体
3. 修改后必须跑 `tests/test_report_slice.py` 确认所有目标 section 仍可切出


## 3. 代码编写约束

### 必须遵守

- 所有新增函数 **必须** 标注参数类型和返回值类型
- 结构化输出 **必须** 使用 `Pydantic` 模型或 `@dataclass`，禁止裸 `dict` 作为接口契约
- LLM 调用失败 **必须** 抛出明确异常，禁止 `try/except pass` 静默吞掉错误
- 配置读取 **必须** 通过 `settings.LLMConfig.from_env()`，禁止 `os.environ["LLM_MODEL_ID"]` 散落在业务代码中
- 日志 **必须** 使用 `logging` 模块，禁止在主线包内使用 `print`

### 禁止行为

| 禁止 | 违反后果 |
|------|----------|
| `from config import *` 或 `import config` | 引入双配置源，配置漂移 |
| 在 extractor 内 `ChatOpenAI(...)` / `ChatOllama(...)` 直接实例化 | 绕过统一配置，无法切换模型 |
| 硬编码模型名、API Key、URL | 无法通过环境变量覆盖 |
| 绕过 `ReportPipeline` 直接调用 `RuleEngineSlicer` / `Extractor` 做生产处理 | 破坏阶段隔离和上下文传递 |
| 修改 `context.py` 中 `ReportContext` / `ReportSection` 的字段结构而不同步更新调用方 | 静默破坏所有依赖该字段的代码 |
| 提交 `__pycache__/`、`.pyc`、`*.egg-info/` | 污染仓库 |

---

## 4. 修改 Pipeline 核心的特殊规则

`pipeline.py` / `context.py` / `settings.py` 是全局依赖，修改这三个文件时：

- **修改前**：必须先通读该文件全文，不允许基于局部片段推断再修改
- **修改时**：每次只改一处语义单元（一个方法或一个类），不允许多处同时改
- **修改后**：必须跑完整 E2E：`python tests/main_pipeline.py`，确认无异常

---

## 5. 任务完成的验收标准

一个任务**必须满足以下全部条件**才算完成，不允许只完成代码修改就结束：

- [ ] 目标功能可通过 `run_until` 分步调试验证
- [ ] 相关测试脚本（`tests/test_report_*.py`）无新增失败
- [ ] 没有引入新的 `print` / 硬编码配置 / 裸 `dict` 接口
- [ ] `STATE.md` 已更新当前断点
- [ ] `ISSUES.md` 中若有关联问题，已标注为已解决或已更新状态

---

## 6. 主线代码位置速查

```
packages/fd-extractai-report/src/fd_extractai_report/
├── pipeline.py                  # 总编排，唯一允许的生产入口
├── context.py                   # ReportContext / ReportSection 定义
├── settings.py                  # LLM 配置，读取环境变量
├── converters/
│   └── markdown_converter.py    # 文档 → Markdown，.doc 依赖 soffice
├── detectors/
│   └── type_detector.py         # house / land / asset 类型检测
├── sections/
│   └── rule_engine_slicer.py    # 规则引擎切片器
├── extractors/
│   ├── base.py                  # Extractor 基类，langextract 封装
│   └── rule_engine_extractor.py # 按规则集顺序执行所有 extractor
├── rules/
│   ├── slicing/                 # 切片规则：schema / default_rulesets / registry
│   └── extracting/              # 抽取规则：schema / default_rulesets / registry
└── prompts/                     # prompt 模板 .txt 文件
```
