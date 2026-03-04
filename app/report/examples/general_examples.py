from __future__ import annotations

from langextract.core import data

from langextract.core import data

 
example_price =  data.ExampleData(
        text="估价结果：总价为100万元，单价为5000元/平方米。",
        extractions=[
            data.Extraction(
                "price_item",
                "总价为100万元",
                attributes={
                    "total_price": 1000000,   # 100万元 => 1,000,000元
                    "unit_price": 5000,
                    "currency": "CNY",
                    "unit": "万元",
                    "raw_text": "总价为100万元，单价为5000元/平方米",
                    "confidence": "medium",
                },
            )
        ],
    )
 

example_purpose = data.ExampleData(
    text="""
估价目的与用途
本次评估目的为确定抵押贷款所需的抵押价值，评估对象为位于长沙市雨花区的房产。
委托方：长沙银行股份有限公司
价值类型：抵押价值（公开市场价值假设）
用途：向金融机构提供抵押担保。
""",
    extractions=[
        data.Extraction(
            "valuation_purpose_item",
            "抵押贷款所需的抵押价值",
            attributes={
                "purpose": "确定抵押贷款抵押价值",
                "value_type": "抵押价值",
                "usage": "贷款抵押",
                "client": "长沙银行股份有限公司",
            },
        )
    ],
)

example_assumption = data.ExampleData(
    text="""
重要假设与限制条件
1. 本次评估假设委估资产权属清晰，不存在任何未披露的权利瑕疵。
2. 评估结果仅对本报告所载明的目的和假设成立。
""",
    extractions=[
        data.Extraction(
            "valuation_assumption",
            "假设委估资产权属清晰",
            attributes={
                "category": "重要假设",
                "description": "委估资产权属清晰，不存在未披露的权利瑕疵。",
            },
        )
    ],
)

example_method = data.ExampleData(
    text="""
估价方法
综合比较市场法与收益法，最终取比较法结果作为评估结论。
比较法主要选取区域内近期成交案例，并对楼层、成新、面积进行修正。
""",
    extractions=[
        data.Extraction(
            "valuation_method",
            "比较法",
            attributes={
                "method": "市场比较法",
                "adjustments": "楼层、成新、面积修正",
                "final_weight": 0.7,
            },
        )
    ],
)

example_conclusion = data.ExampleData(
    text="""
估价结论
价值时点：2025年8月30日
估价总价：人民币 8,560,000 元（捌佰捌拾陆万元整）
单价：12,800 元/㎡
""",
    extractions=[
        data.Extraction(
            "valuation_conclusion",
            "估价结论",
            attributes={
                "value_date": "2025-08-30",
                "total_value": 8560000,
                "unit_price": 12800,
            },
        )
    ],
)

GENERAL_EXAMPLES = {
    "price":[example_price],
    "purpose": [example_purpose],
    "assumptions": [example_assumption],
    "method": [example_method],
    "conclusion": [example_conclusion],
}

