from __future__ import annotations

from langextract.core import data

example_valuation_result = data.ExampleData(
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
            "valuation_target_item", 
            "洪房权证黔城镇字第711000391号", # 锚点：权证号
            attributes={ 
                "object_num":"估价对象1",
                "certificate_number": "洪房权证黔城镇字第711000391号",
                "owner_name": "肖春梅",
                "building_area": 61.99, # 建议使用数字类型
                "usage": "商业",
                "total_price": 219135
            }
        )
    ]
)  

example_valuation_dispersed = data.ExampleData(
    text="""
    估价对象基本情况一览表
    | 名称 | 坐落 | 规划用途 | 权证号码 | 产权人 | 产权面积（㎡） |
    | --- | --- | --- | --- | --- | --- |
    | 保利天禧 | 岳麓区... | 办公 | 湘(2023)长沙市不动产权第0386909号 | 杨瑾 | 40.75 |
    
    估价结果汇总表
    | 项目及结果 | | 结果 |
    | --- | --- | --- |
    | 1.假定未设立法定优先受偿权下的价值 | 总价（元） | 313816 |
    """,
    extractions=[
        data.Extraction(
            "valuation_target_item",
            "湘(2023)长沙市不动产权第0386909号",
            attributes={
                "object_num": "估价对象1",
                "certificate_number": "湘(2023)长沙市不动产权第0386909号",
                "owner_name": "杨瑾",
                "building_area": 40.75,
                "usage": "办公",
                "total_price": 313816
            }
        )
    ]
)

VALUATION_EXAMPLES = [example_valuation_result, example_valuation_dispersed]

