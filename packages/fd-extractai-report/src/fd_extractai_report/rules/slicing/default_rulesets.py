from __future__ import annotations

from fd_extractai_report.rules.slicing.schema import SliceRuleSet, SliceStep

# ????? key ??? extractor.target_slice_key / input_slice_keys ??
# purpose / assumptions / method / conclusion / targets_section / valuation_tables ?

ruleset_house = SliceRuleSet(
    name="house_v1",
    defaults={
        "dedup": True,
        "max_chars": 10000,
    },
    steps=[
       SliceStep(
            key="cover",
            mode="by_regex_between",
            # ? starts??????????/?????????
            targets=[
                r"?????????",
                r"?????",
            ],
            params={
                "ends": [
                    r"???????",
                    r"??????",]
                ,
                 "loose_space": True,
                "pick": "earliest",           # ?????? start?end ????
                "include_start": True,
                "include_end": False,
                "fallback_end_chars": 12000,  # ??? end ??? start+12000???
                "merge": True,
                "max_chars": 0,            # ?? defaults ????????????
            },
            missing="empty",
        ),
        SliceStep(
            key="summary",
            mode="by_regex_between",
            targets=[
                r"???????",
                r"??????",
                r"?????",
                r"??",
            ],
            params={
                "ends": [
                    r"??"
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # ??????????????????
                "include_end": False,
                "fallback_end_chars": 6000,  # ??????
                "merge": True,
                "max_chars": 0,       # ?????????? defaults               
                    },
            missing="empty",
        ),
         SliceStep(
            key="object",
            mode="by_segment_tables",
            within="summary",
            targets=[
                r"???????????",     
                r"????.*???",                      
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
                r"???????",     
                r"???????"           
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
                r"??????",
                r"????",
            ],
            params={
                "ends": [
                    r"????",
                    r"??",
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
                r"????",
                r"??",
            ],
            params={
                "ends": [
                    r"????",
                    r"??????",
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # ??????????????????
                "include_end": False,
                "fallback_end_chars": 8000,  # ??????
                "merge": True,
                "max_chars": 12000,       # ?????????? defaults              
            },
            missing="empty",
        ),
        SliceStep(
            key="price",
            mode="by_regex_between",
            within="summary",
            targets=[
                r"????",
            ],
            params={
                "ends": [
                    r"?????",                    
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": False,   # ??????????????????
                "include_end": False,
                "fallback_end_chars": 8000,  # ??????
                "merge": True,
                "max_chars": 12000,       # ?????????? defaults              
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
                r"???????",
                r"???????????????",
            ],
            params={
                "ends": [
                    r"????",
                    r"??",
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,
                "include_end": False,
                "fallback_end_chars": 15000,  # ??????????
                "merge": True,
                "max_chars": 22000,
            },
            missing="empty",
        ),
        SliceStep(
            key="summary",
            mode="by_regex_between",
            targets=[
                r"????????",
                r"??",
            ],
            params={
                "ends": [
                    r"????????",
                    r"????",
                ],
                "loose_space": True,
                "pick": "earliest",
                "include_start": True,   # ??????????????????
                "include_end": False,
                "fallback_end_chars": 6000,  # ??????
                "merge": True,
                "max_chars": 2500,       # ?????????? defaults
                "skip_if_line_matches": [
                    r"^\s*\[.*\]\(#",          # [xxx](#anchor)
                    r"^\s*\[.*\]\(__",         # [xxx](#__RefHeading___Toc...)
                ],
            },
            missing="empty",
        ),
    ],
)

ruleset_checklist = SliceRuleSet(
    name="checklist_v1",
    defaults={"dedup": True, "max_chars": 50000},
    steps=[
        SliceStep(
            key="items",
            mode="by_window_after",
            targets=[r"\S"],
            params={
                "anchor_regex": True,
                "anchor_pick": "earliest",
                "window_chars": 50000,
                "max_chars": 50000,
            },
            missing="full",
        ),
    ],
)

DEFAULT_RULESETS_BY_TYPE = {
    "house": ruleset_house,
    "land": ruleset_land,
    "asset": ruleset_asset,
    "checklist": ruleset_checklist,
}
