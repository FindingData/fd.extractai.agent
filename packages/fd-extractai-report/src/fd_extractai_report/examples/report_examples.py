from __future__ import annotations

from typing import Dict, List, Literal
from langextract.core import data

ReportType = Literal["house", "land", "asset"]

# =========================================================
# 1) PURPOSE / ASSUMPTIONS / METHOD / CONCLUSION（按类型）
# =========================================================

# -------- HOUSE --------
house_example_price = data.ExampleData(
    text="""
本公司根据估价目的，遵循估价原则，采用科学合理的估价方法，在认真分析现有资料的基础上，经过测算，结合估价经验与对影响房地产市场价格因素进行分析，确定估价对象在市场上有足够的买方和卖方，并且进入市场无障碍的条件下，于价值时点的假定未设立法定优先受偿权下的市场价值单价为7554元/平方米，总价为112.04万元，估价师知悉的法定优先受偿款为0元，最后确定委评房地产的抵押价值单价为7554元/平方米，总价为112.04万元（大写：人民币壹佰壹拾贰万零肆佰元整)。估价结果汇总如下表所示。
""",
    extractions=[
        data.Extraction(
            "price_item",
            "总价为112.04万元",
            attributes={
                # ✅ 统一口径：总价用“元”
                "total_price": 1120400,          # 112.04 万元 => 1,120,400 元
                "unit_price": 7554,              # 元/㎡                
                "raw_text": "市场价值单价为7554元/平方米，总价为112.04万元；抵押价值单价为7554元/平方米，总价为112.04万元",
                "report_type": "house",
                "confidence": "high",
            },
        )
    ],
)


house_example_result = data.ExampleData(
    text="""
| 估价对象 | 权证号 | 权利人 | 坐落 | 用途 | 所在层/总层数 | 建筑面积（m2） | 单价（元/m2) | 总价（元） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 洪房权证黔城镇字第711000391号 | 肖春梅 | 洪江市黔城镇玉壶路交通局隔壁01、02等2套 | 商业 | 1/6 | 61.99 | 3535 | 219135 |
| 2 | 洪房权证黔城镇字第711000390号 | 肖春梅 | 洪江市黔城镇玉壶路交通局隔壁03、04等2套 | 商业 | 1/6 | 61.99 | 3535 | 219135 |
| 3 | 洪房权证黔城字第715001640号 | 肖春梅 | 洪江市黔城镇玉壶路（交通局隔壁） | 商业 | 1/6 | 77.04 | 3535 | 272336 |
| 4 | 洪房权证黔字第2009-0878号 | 徐文相 | 洪江市黔城镇玉壶路（交通局隔壁）111、112 | 商业 | 1/6 | 77.04 | 3535 | 272336 |

""",
    extractions=[
       # 仅定义第一条记录的结构
        data.Extraction(
            "result_item", 
            "洪房权证黔城镇字第711000391号", # 锚点：权证号
            attributes={ 
                "certificate_number": "洪房权证黔城镇字第711000391号",
                "owner_name": "肖春梅",
                "building_area": 61.99,
                "usage": "商业",
                "total_price": 219135,
                "location": "洪江市黔城镇玉壶路交通局隔壁01、02等2套",          # 可选
                "floor_info": "1/6",        # 可选
                "unit_price": 3535          # 可选
            }
        )
    ]
)  


house_example_purpose = data.ExampleData(
    text="""
估价目的与用途
本次估价目的为确定抵押贷款所需的房地产抵押价值。
估价对象为位于长沙市雨花区的住宅/商业用房。
委托方：长沙银行股份有限公司
价值类型：抵押价值（公开市场价值假设）
用途：向金融机构提供抵押担保。
""",
    extractions=[
        data.Extraction(
            "valuation_purpose_item",
            "抵押贷款所需的房地产抵押价值",
            attributes={
                "purpose": "确定抵押贷款抵押价值",
                "value_type": "抵押价值",
                "usage": "贷款抵押",
                "client": "长沙银行股份有限公司",
                "report_type": "house",
            },
        )
    ],
)

house_example_method = data.ExampleData(
    text="""
估价方法
本次估价采用市场比较法，并结合收益法进行校核。
比较法选取同区域近期成交案例，对楼层、朝向、成新、面积等因素进行修正。
最终以市场比较法结果作为估价结论依据。
""",
    extractions=[
        data.Extraction(
            "valuation_method",
            "市场比较法",
            attributes={
                "method": "市场比较法",
                "adjustments": "楼层、朝向、成新、面积修正",
                "final_method": "市场比较法",
                "report_type": "house",
            },
        )
    ],
)

house_example_conclusion = data.ExampleData(
    text="""
估价结论
价值时点：2025年8月30日
估价总价：人民币 8,560,000 元（捌佰伍拾陆万元整）
单价：12,800 元/㎡
""",
    extractions=[
        data.Extraction(
            "valuation_conclusion",
            "估价总价：人民币 8,560,000 元",
            attributes={
                "value_date": "2025-08-30",
                "total_value": 8560000,
                "unit_price": 12800,
                "currency": "CNY",
                "report_type": "house",
            },
        )
    ],
)

house_example_assumption = data.ExampleData(
    text="""
重要假设与限制条件
1. 估价对象权属清晰，不存在未披露的权利瑕疵。
2. 估价对象不存在影响价值的重大质量缺陷，正常使用与维护条件下成立。
3. 本报告仅为抵押目的使用，未经许可不得用于其他用途。
""",
    extractions=[
        data.Extraction(
            "valuation_assumption",
            "估价对象权属清晰",
            attributes={
                "category": "重要假设",
                "description": "估价对象权属清晰，不存在未披露的权利瑕疵。",
                "report_type": "house",
            },
        )
    ],
)

# -------- LAND --------
land_example_price = data.ExampleData(
    text="""
估价对象：
① 未设定法定优先受偿款权下的市场价格：
土地面积6893.10 平方米；
单位地价：350元/㎡；
总 地 价：2412585 元；
大写：人民币贰佰肆拾壹万贰仟伍佰捌拾伍元整；
② 估价师知悉的法定优先受偿款为：零。
③ 估价对象的抵押总价为：
土地面积6893.10 平方米；
单位地价：350元/㎡；
总 地 价：2412585 元；
大写：人民币贰佰肆拾壹万贰仟伍佰捌拾伍元整；
估价结果详见附表《土地估价结果一览表》（表1-1）。
""",
    extractions=[
        data.Extraction(
            "price_item",
            "总 地 价：2412585 元",
            attributes={
                # ✅ 已经是元，直接用
                "total_price": 2412585,
                "unit_price": 350,
                "raw_text": "土地面积6893.10平方米；单位地价：350元/㎡；总地价：2412585元；抵押总价：2412585元",
                "report_type": "land",
                "confidence": "high",
            },
        )
    ],
)

land_example_purpose = data.ExampleData(
    text="""
估价目的与用途
本次估价目的为确定宗地土地使用权在估价期日的出让土地使用权价值。
委托方：长沙市某某自然资源局
估价对象：某宗地（国有建设用地使用权）
价值类型：市场价值
用途：用于土地出让/抵押/资产处置参考。
""",
    extractions=[
        data.Extraction(
            "valuation_purpose_item",
            "出让土地使用权价值",
            attributes={
                "purpose": "确定宗地土地使用权价值",
                "value_type": "市场价值",
                "usage": "土地出让/处置参考",
                "client": "长沙市某某自然资源局",
                "report_type": "land",
            },
        )
    ],
)

land_example_method = data.ExampleData(
    text="""
估价方法
本次土地估价采用基准地价修正法与市场比较法相结合。
根据宗地规划用途、容积率、开发程度（五通一平）、出让年限等因素进行修正测算。
最终综合判定宗地地价水平。
""",
    extractions=[
        data.Extraction(
            "valuation_method",
            "基准地价修正法",
            attributes={
                "method": "基准地价修正法",
                "secondary_method": "市场比较法",
                "adjustments": "规划用途、容积率、开发程度（五通一平）、出让年限修正",
                "report_type": "land",
            },
        )
    ],
)

land_example_conclusion = data.ExampleData(
    text="""
估价结论
估价期日：2025年8月30日
宗地面积：10,000.00 ㎡
宗地总地价：人民币 12,300,000 元
地价水平：1,230 元/㎡
""",
    extractions=[
        data.Extraction(
            "valuation_conclusion",
            "宗地总地价：人民币 12,300,000 元",
            attributes={
                "value_date": "2025-08-30",
                "land_area": 10000.00,
                "total_value": 12300000,
                "unit_price": 1230,  # 元/㎡
                "currency": "CNY",
                "report_type": "land",
            },
        )
    ],
)

land_example_assumption = data.ExampleData(
    text="""
重要假设与限制条件
1. 宗地权属界址清楚，土地权属无争议。
2. 规划条件及容积率等指标以政府主管部门出具文件为准。
3. 宗地开发程度按报告所述“五通一平”现状成立。
""",
    extractions=[
        data.Extraction(
            "valuation_assumption",
            "宗地权属界址清楚",
            attributes={
                "category": "重要假设",
                "description": "宗地权属界址清楚，土地权属无争议。",
                "report_type": "land",
            },
        )
    ],
)

# -------- ASSET --------
from langextract.core import data

asset_example_price = data.ExampleData(
    text="""
八、评估结论：经实施评估程序后，于评估基准日，委估专利权的市场价值评估值为：人民币壹仟贰佰伍拾陆万肆仟伍佰元整（￥1,256.45万元），详细情况见资产评估明细表。
""",
    extractions=[
        data.Extraction(
            "price_item",
            "（￥1,256.45万元）",
            attributes={
                # ✅ 总价统一为“元”
                "total_price": 12564500,   # 1,256.45 万元 => 12,564,500 元
                "unit_price":0,
                "unit": "万元",
                "raw_text": "委估专利权的市场价值评估值为：人民币壹仟贰佰伍拾陆万肆仟伍佰元整（￥1,256.45万元）",
                "report_type": "asset",
                "confidence": "high",
            },
        )
    ],
)

asset_example_purpose = data.ExampleData(
    text="""
评估目的与用途
本次资产评估目的为确定某公司股东全部权益价值，为股权转让提供价值参考。
委托方：某某有限公司
评估基准日：2025年8月30日
价值类型：市场价值
用途：股权转让/改制/增资扩股参考。
""",
    extractions=[
        data.Extraction(
            "valuation_purpose_item",
            "确定某公司股东全部权益价值",
            attributes={
                "purpose": "确定股东全部权益价值",
                "value_type": "市场价值",
                "usage": "股权转让/增资参考",
                "client": "某某有限公司",
                "base_date": "2025-08-30",
                "report_type": "asset",
            },
        )
    ],
)

asset_example_method = data.ExampleData(
    text="""
评估方法
本次评估采用收益法与资产基础法。
对企业未来收益进行预测并折现，同时对各项资产（机器设备、无形资产等）进行清查评估。
最终以收益法结果为主，资产基础法为辅进行综合判断。
""",
    extractions=[
        data.Extraction(
            "valuation_method",
            "收益法",
            attributes={
                "method": "收益法",
                "secondary_method": "资产基础法",
                "adjustments": "收益预测与折现参数；资产清查（机器设备、无形资产）",
                "final_method": "收益法",
                "report_type": "asset",
            },
        )
    ],
)

asset_example_conclusion = data.ExampleData(
    text="""
评估结论
评估基准日：2025年8月30日
股东全部权益价值：人民币 56,800,000 元
""",
    extractions=[
        data.Extraction(
            "valuation_conclusion",
            "股东全部权益价值：人民币 56,800,000 元",
            attributes={
                "value_date": "2025-08-30",
                "equity_value": 56800000,
                "currency": "CNY",
                "report_type": "asset",
            },
        )
    ],
)

asset_example_assumption = data.ExampleData(
    text="""
重要假设与限制条件
1. 委估资产权属清晰，不存在未披露的权利瑕疵。
2. 企业持续经营假设成立，财务资料真实、完整、合法。
3. 评估结果仅用于本报告所载明目的，不得用于其他用途。
""",
    extractions=[
        data.Extraction(
            "valuation_assumption",
            "企业持续经营假设成立",
            attributes={
                "category": "重要假设",
                "description": "企业持续经营假设成立，财务资料真实、完整、合法。",
                "report_type": "asset",
            },
        )
    ],
)

# =========================================================
# 2) TARGET ITEMS（按类型：房产/土地/资产）
# =========================================================

# -------- HOUSE targets：表格型（权证/权利人/面积/用途/单价/总价）--------
house_example_targets_table = data.ExampleData(
    text="""
| 估价对象 | 权证号 | 权利人 | 坐落 | 用途 | 所在层/总层数 | 建筑面积（㎡） | 单价（元/㎡） | 总价（元） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 湘(2023)长沙市不动产权第0386909号 | 杨瑾 | 岳麓区xxx路xx号 | 办公 | 8/32 | 40.75 | 7700 | 313816 |
""",
    extractions=[
        data.Extraction(
            "valuation_target_item",
            "湘(2023)长沙市不动产权第0386909号",
            attributes={
                "object_num": "1",
                "certificate_number": "湘(2023)长沙市不动产权第0386909号",
                "owner_name": "杨瑾",
                "location": "岳麓区xxx路xx号",
                "usage": "办公",
                "floor": "8/32",
                "building_area": 40.75,
                "unit_price": 7700,
                "total_price": 313816,
                "report_type": "house",
            },
        )
    ],
)

# -------- LAND targets：宗地信息（宗地号/用途/面积/容积率/年限/地价）--------
land_example_targets = data.ExampleData(
    text="""
宗地基本情况一览表
| 宗地号 | 坐落 | 用地性质/用途 | 宗地面积（㎡） | 容积率 | 出让年限（年） | 开发程度 | 地价（元/㎡） | 宗地总地价（元） |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: |
| 430100-2025-001 | 长沙市xx区xx路 | 商服用地 | 10000.00 | 3.0 | 40 | 五通一平 | 1230 | 12300000 |
""",
    extractions=[
        data.Extraction(
            "valuation_target_item",
            "430100-2025-001",
            attributes={
                "parcel_id": "430100-2025-001",
                "location": "长沙市xx区xx路",
                "usage": "商服用地",
                "land_area": 10000.00,
                "plot_ratio": 3.0,
                "lease_years": 40,
                "development": "五通一平",
                "unit_price": 1230,
                "total_price": 12300000,
                "report_type": "land",
            },
        )
    ],
)

# -------- ASSET targets：资产清单/评估对象（设备/无形资产/账面/评估值）--------
asset_example_targets = data.ExampleData(
    text="""
资产评估对象明细（节选）
| 序号 | 资产类别 | 名称 | 数量 | 账面价值（元） | 评估价值（元） |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | 机器设备 | 数控机床 | 2 | 1,200,000 | 1,350,000 |
| 2 | 无形资产 | 专利权 | 1 | 0 | 5,800,000 |
""",
    extractions=[
        data.Extraction(
            "valuation_target_item",
            "数控机床",
            attributes={
                "asset_category": "机器设备",
                "asset_name": "数控机床",
                "quantity": 2,
                "book_value": 1200000,
                "assessed_value": 1350000,
                "report_type": "asset",
            },
        )
    ],
)

# =========================================================
# 3) 汇总：按 report_type 组织 examples
#    你后续：根据 context.metadata["report_type"] 选择对应 examples
# =========================================================

EXAMPLES_BY_TYPE: Dict[ReportType, Dict[str, List[data.ExampleData]]] = {
    "house": {
        "price":[house_example_price],
        "result":[house_example_result],
        "purpose": [house_example_purpose],
        "assumptions": [house_example_assumption],
        "method": [house_example_method],
        "conclusion": [house_example_conclusion],
        "targets": [house_example_targets_table],
    },
    "land": {
        "price":[land_example_price],
        "purpose": [land_example_purpose],
        "assumptions": [land_example_assumption],
        "method": [land_example_method],
        "conclusion": [land_example_conclusion],
        "targets": [land_example_targets],
    },
    "asset": {
         "price":[asset_example_price],        
        "purpose": [asset_example_purpose],
        "assumptions": [asset_example_assumption],
        "method": [asset_example_method],
        "conclusion": [asset_example_conclusion],
        "targets": [asset_example_targets],
    },
}