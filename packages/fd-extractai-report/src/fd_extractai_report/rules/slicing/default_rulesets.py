from __future__ import annotations

from fd_extractai_report.rules.slicing.schema import SliceRuleSet, SliceStep

# 建议：这些 key 尽量与 extractor.target_slice_key / input_slice_keys 对齐
# purpose / assumptions / method / conclusion / targets_section / valuation_tables 等

ruleset_house = SliceRuleSet(
    name="house_v1",
    defaults={
        "dedup": True,
        "max_chars": 1000,
    },
    steps=[
       SliceStep(
            key="cover",
            mode="by_regex_between",
            # ✅ starts：尽量用“封面第一行/主标题”这类强特征
            targets=[
                r"房地产抵押估价报告",
                r"房地产估价",
            ],
            params={
                "ends": [
                    r"致估价委托人函",
                    r"估价委托人函",]
                ,
                 "loose_space": True,
                "pick": "earliest",           # 找最早出现的 start；end 也找最早
                "include_start": True,
                "include_end": False,
                "fallback_end_chars": 12000,  # 找不到 end 就截到 start+12000，防爆
                "merge": True,
                "max_chars": 0,            # 覆盖 defaults 也可以不写（这里写清楚）
            },
            missing="empty",
        ),
        SliceStep(
            key="summary",
            mode="by_regex_between",
            targets=[
                r"致估价委托人函",
                r"估价委托人函",
                r"致委托人函",
                r"致函",
            ],
            params={
                "ends": [
                    r"目录"
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # 保留“摘要”标题（方便你后续抽字段）
                "include_end": False,
                "fallback_end_chars": 6000,  # 摘要一般不长
                "merge": True,
                "max_chars": 0,       # 摘要上限：建议稍大于 defaults               
                    },
            missing="empty",
        ),
         SliceStep(
            key="object",
            mode="by_segment_tables",
            within="summary",
            targets=[
                r"估价对象基本情况一览表",     
                r"估价对象.*一览表",                      
            ],
            params={
                "max_table_chars": 12000,
                "min_table_rows": 3,
            }
            ),
        SliceStep(
            key="result",
            mode="by_segment_tables",
            within="summary",
            targets=[
                r"估价结果一览表",     
                r"估价结果汇总表"           
            ],
            params={
                "max_table_chars": 12000,
                "min_table_rows": 3,
            }
            ),
    ],    
)

ruleset_land = SliceRuleSet(
    name="land_v1",
    defaults={"dedup": True, "max_chars": 10000},
    steps=[
        SliceStep(
            key="cover",
            mode="by_regex_between",
            targets=[
                r"土地估价报告",
                r"土地估价",
            ],
            params={
                "ends": [
                    r"第一部分",
                    r"摘要",
                ],
                 "loose_space": True,
                "pick": "earliest",
                "include_start": True,
                "include_end": False,
                "fallback_end_chars": 12000,
                "merge": True,
                "max_chars": 12000,
            },
            missing="empty",
        ),
        SliceStep(
            key="summary",
            mode="by_regex_between",
            targets=[
                r"第一部分",
                r"摘要",
            ],
            params={
                "ends": [
                    r"第二部份",
                    r"估价对象界定",
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # 保留“摘要”标题（方便你后续抽字段）
                "include_end": False,
                "fallback_end_chars": 8000,  # 摘要一般不长
                "merge": True,
                "max_chars": 12000,       # 摘要上限：建议稍大于 defaults              
            },
            missing="empty",
        ),
    ],
)

ruleset_asset = SliceRuleSet(
    name="asset_v1",
    defaults={"dedup": True, "max_chars": 22000},
    steps=[
        SliceStep(
            key="cover",
            mode="by_regex_between",
            targets=[
                r"资产评估报告书",
                r"资产评估",
            ],
            params={
                "ends": [
                    r"本册目录",
                    r"声明",
                ],
                 "loose_space": True,
                "pick": "earliest",
                "include_start": True,
                "include_end": False,
                "fallback_end_chars": 15000,  # 资产封面可能更长一点
                "merge": True,
                "max_chars": 22000,
            },
            missing="empty",
        ),
        SliceStep(
            key="summary",
            mode="by_regex_between",
            targets=[
                r"资产评估报告摘要",
                r"摘要",
            ],
            params={
                "ends": [
                    r"资产评估报告正文",
                    r"报告正文",
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # 保留“摘要”标题（方便你后续抽字段）
                "include_end": False,
                "fallback_end_chars": 6000,  # 摘要一般不长
                "merge": True,
                "max_chars": 2500,       # 摘要上限：建议稍大于 defaults
                "skip_if_line_matches": [
                    r"^\s*\[.*\]\(#",          # [xxx](#anchor)
                    r"^\s*\[.*\]\(__",         # [xxx](#__RefHeading___Toc...)
                ],
            },
            missing="empty",
        ),
    ],
)

DEFAULT_RULESETS_BY_TYPE = {
    "house": ruleset_house,
    "land": ruleset_land,
    "asset": ruleset_asset,
}