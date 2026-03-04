from __future__ import annotations

from fd_extractai_report.rules.slicing.schema import SliceRuleSet, SliceStep

# 建议：这些 key 尽量与 extractor.target_slice_key / input_slice_keys 对齐
# purpose / assumptions / method / conclusion / targets_section / valuation_tables 等

ruleset_house = SliceRuleSet(
    name="house_v1",
    defaults={
        "dedup": True,
        "max_chars": 20000,
    },
    steps=[
        SliceStep(
            key="purpose",
            mode="by_heading",
            targets=["估价目的与用途", "评估目的与用途"],
            params={"merge": True, "max_chars": 12000},
        ),
        SliceStep(
            key="assumptions",
            mode="by_heading",
            targets=["重要假设与限制条件", "假设与限制条件"],
            params={"merge": True, "max_chars": 14000},
        ),
        SliceStep(
            key="method",
            mode="by_heading",
            targets=["估价方法", "评估方法"],
            params={"merge": True, "max_chars": 12000},
        ),
        SliceStep(
            key="conclusion",
            mode="by_heading",
            targets=["估价结论", "评估结论"],
            params={"merge": True, "max_chars": 12000},
        ),

        # 先把“估价对象/结果相关章节”切出来（后面用于 within 抓表）
        SliceStep(
            key="targets_section",
            mode="by_heading",
            targets=["估价对象", "估价结果", "估价结果一览表", "估价对象基本情况", "估价对象情况"],
            params={"merge": True, "max_chars": 25000},
            missing="empty",
        ),
        # 在 targets_section 内继续抓表
        SliceStep(
            key="valuation_tables",
            mode="by_table_after",
            within="targets_section",
            targets=["估价结果一览表", "估价结果汇总表", "估价对象一览表", "估价结果列表"],
            params={"max_table_chars": 12000, "min_table_rows": 3, "dedup": True, "max_sections": 6},
            missing="empty",
        ),
    ],
)

ruleset_land = SliceRuleSet(
    name="land_v1",
    defaults={"dedup": True, "max_chars": 22000},
    steps=[
        SliceStep(key="purpose", mode="by_heading", targets=["估价目的与用途"], params={"merge": True, "max_chars": 12000}),
        SliceStep(key="assumptions", mode="by_heading", targets=["重要假设与限制条件"], params={"merge": True, "max_chars": 14000}),
        SliceStep(key="method", mode="by_heading", targets=["估价方法"], params={"merge": True, "max_chars": 12000}),
        SliceStep(key="conclusion", mode="by_heading", targets=["估价结论"], params={"merge": True, "max_chars": 12000}),
        SliceStep(
            key="targets_section",
            mode="by_heading",
            targets=["宗地基本情况", "宗地基本情况一览表", "宗地信息", "估价结果一览表"],
            params={"merge": True, "max_chars": 26000},
        ),
        SliceStep(
            key="valuation_tables",
            mode="by_table_after",
            within="targets_section",
            targets=["宗地基本情况一览表", "估价结果一览表", "宗地信息一览表"],
            params={"max_table_chars": 12000, "min_table_rows": 3, "dedup": True, "max_sections": 8},
        ),
    ],
)

ruleset_asset = SliceRuleSet(
    name="asset_v1",
    defaults={"dedup": True, "max_chars": 22000},
    steps=[
        SliceStep(key="purpose", mode="by_heading", targets=["评估目的与用途", "估价目的与用途"], params={"merge": True, "max_chars": 12000}),
        SliceStep(key="assumptions", mode="by_heading", targets=["重要假设与限制条件"], params={"merge": True, "max_chars": 14000}),
        SliceStep(key="method", mode="by_heading", targets=["评估方法", "估价方法"], params={"merge": True, "max_chars": 12000}),
        SliceStep(key="conclusion", mode="by_heading", targets=["评估结论", "估价结论"], params={"merge": True, "max_chars": 12000}),
        SliceStep(
            key="targets_section",
            mode="by_heading",
            targets=["资产评估对象", "评估对象", "资产清单", "资产评估对象明细"],
            params={"merge": True, "max_chars": 26000},
        ),
        SliceStep(
            key="valuation_tables",
            mode="by_table_after",
            within="targets_section",
            targets=["资产评估对象明细", "资产清单", "评估对象明细"],
            params={"max_table_chars": 12000, "min_table_rows": 3, "dedup": True, "max_sections": 10},
        ),
    ],
)

DEFAULT_RULESETS_BY_TYPE = {
    "house": ruleset_house,
    "land": ruleset_land,
    "asset": ruleset_asset,
}