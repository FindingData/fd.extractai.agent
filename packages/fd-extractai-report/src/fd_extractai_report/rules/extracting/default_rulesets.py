# app/report/rules/extracting/default_rulesets.py
from __future__ import annotations

from fd_extractai_report.rules.extracting.schema import ExtractRuleSet, ExtractorSpec
from fd_extractai_report.examples.report_examples import EXAMPLES_BY_TYPE
from fd_extractai_report.examples.general_examples import GENERAL_EXAMPLES


# -----------------------------
# house
# -----------------------------
ruleset_house = ExtractRuleSet(
    name="house_default",
    report_type="house",
    inject_context_fields=["report_type"],
    max_input_chars=12000,    
    extractors=[
        ExtractorSpec(
            slug="cover",
            prompt_filename="cover_prompt.txt",
            # ✅ 房产：价值结论/估价结果通常在 summary / conclusion / valuation 一类
            input_slice_keys=["cover"],
            missing_slice_policy="full",
            max_input_chars=9000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "house": EXAMPLES_BY_TYPE["house"]["cover"],
            },
            output_key="cover",
        ),
        ExtractorSpec(
            slug="price",
            prompt_filename="price_prompt.txt",
            # ✅ 房产：价值结论/估价结果通常在 summary / conclusion / valuation 一类
            input_slice_keys=["summary"],
            missing_slice_policy="full",
            max_input_chars=9000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "house": EXAMPLES_BY_TYPE["house"]["price"],
            },
            output_key="price",
        ),
         ExtractorSpec(
            slug="object",
            prompt_filename="house_object_prompt.txt",
            # ✅ 房产：价值结论/估价结果通常在 summary / conclusion / valuation 一类
            input_slice_keys=["object"],
            missing_slice_policy="full",
            max_input_chars=12000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "house": EXAMPLES_BY_TYPE["house"]["object"],
            },
            output_key="object",
        ),
         ExtractorSpec(
            slug="result",
            prompt_filename="house_result_prompt.txt",
            # ✅ 房产：价值结论/估价结果通常在 summary / conclusion / valuation 一类
            input_slice_keys=["result"],
            missing_slice_policy="empty",             
            max_input_chars=12000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "house": EXAMPLES_BY_TYPE["house"]["result"],
            },
            output_key="result",
        ),
    ],
)


# -----------------------------
# land
# -----------------------------
ruleset_land = ExtractRuleSet(
    name="land_default",
    report_type="land",
    inject_context_fields=["report_type"],
    max_input_chars=12000,
    extractors=[
        ExtractorSpec(
            slug="price",
            prompt_filename="land_price_prompt.txt",
            # ✅ 土地：经常有“土地估价结果一览表/估价对象/估价结果”等段落
            input_slice_keys=["price"],
            missing_slice_policy="full",
            max_input_chars=9000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "land": EXAMPLES_BY_TYPE["land"]["price"],
            },
            output_key="price",
        ),
    ],
)


# -----------------------------
# asset
# -----------------------------
ruleset_asset = ExtractRuleSet(
    name="asset_default",
    report_type="asset",
    inject_context_fields=["report_type"],
    max_input_chars=12000,
    extractors=[
        ExtractorSpec(
            slug="price",
            prompt_filename="price_prompt.txt",
            # ✅ 资产：常见“评估结论/评估结果/结论”段
            input_slice_keys=["summary"],
            missing_slice_policy="full",
            max_input_chars=12000,
            defaults={},
            inject_context_fields=["report_type"],
            examples={
                "asset": EXAMPLES_BY_TYPE["asset"]["price"],
            },
            output_key="price",
        ),
    ],
)


DEFAULT_RULESETS = {
    "house": ruleset_house,
    "land": ruleset_land,
    "asset": ruleset_asset,
}