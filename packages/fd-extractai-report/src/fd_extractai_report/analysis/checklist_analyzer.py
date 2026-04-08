from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from fd_extractai_report.settings import CONFIG, LLMConfig

logger = logging.getLogger(__name__)

_CATEGORY_ORDER = [
    "权属证明",
    "规划许可",
    "项目资料",
    "交易案例",
    "价格标准",
    "税费政策",
    "测绘验收",
    "委托文件",
    "其他",
]

_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("权属证明", ["不动产权证", "房屋所有权证", "土地使用权证", "国有土地使用证", "权属"]),
    ("规划许可", ["规划", "许可", "控规", "国土空间", "总平面图"]),
    ("项目资料", ["项目", "函", "资料", "清单", "说明", "图件"]),
    ("交易案例", ["交易", "成交", "案例", "租赁", "二手房", "挂牌"]),
    ("价格标准", ["基准地价", "标定地价", "重置价", "造价", "指标", "地价"]),
    ("税费政策", ["税", "费", "补偿", "出让金", "政策", "征地"]),
    ("测绘验收", ["测绘", "验收", "竣工"]),
    ("委托文件", ["委托", "合同"]),
]


class ChecklistAnalyzer:
    """对 checklist 抽取结果做本地去重、归并、分类，并输出 JSON/Markdown。"""

    def __init__(self, llm_config: Optional[LLMConfig] = None) -> None:
        self._cfg = llm_config or CONFIG

    @staticmethod
    def _pick_name(item: Dict[str, Any]) -> str:
        return str(
            item.get("item_name")
            or item.get("content")
            or item.get("group")
            or ""
        ).strip()

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = re.sub(r"\s+", "", name or "")
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = re.sub(r"[;；。,.，：:]+$", "", normalized)
        return normalized.strip()

    @staticmethod
    def _classify(name: str, group: str) -> str:
        haystack = f"{group} {name}".strip()
        for category, keywords in _CATEGORY_RULES:
            if any(keyword in haystack for keyword in keywords):
                return category
        return "其他"

    def analyze(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []

        merged: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

        for item in items:
            raw_name = self._pick_name(item)
            if not raw_name:
                continue

            canonical_name = self._normalize_name(raw_name)
            if not canonical_name:
                continue

            group = str(item.get("group") or "").strip()
            category = self._classify(canonical_name, group)
            entry = merged.setdefault(
                canonical_name,
                {
                    "category": category,
                    "canonical_name": canonical_name,
                    "aliases": [],
                    "frequency": 0,
                },
            )

            alias_candidates = [raw_name]
            if group:
                alias_candidates.append(group)

            for alias in alias_candidates:
                alias = str(alias).strip()
                if alias and alias not in entry["aliases"]:
                    entry["aliases"].append(alias)

            entry["frequency"] += 1

        results = list(merged.values())
        logger.info("checklist analyze: %d items -> %d deduplicated", len(items), len(results))
        return results

    def to_markdown(
        self,
        analyzed: List[Dict[str, Any]],
        title: str = "资料清单汇总（去重分类）",
    ) -> str:
        if not analyzed:
            return "_无分析结果_\n"

        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for item in analyzed:
            category = str(item.get("category") or "其他").strip()
            by_category.setdefault(category, []).append(item)

        sorted_categories = sorted(
            by_category.keys(),
            key=lambda value: _CATEGORY_ORDER.index(value)
            if value in _CATEGORY_ORDER
            else len(_CATEGORY_ORDER),
        )

        lines: List[str] = [f"# {title}", ""]
        for category in sorted_categories:
            lines.append(f"## {category}")
            lines.append("")
            lines.append("| 标准名称 | 出现次数 | 原始别名 |")
            lines.append("|---|---:|---|")

            for item in by_category[category]:
                canonical_name = str(item.get("canonical_name") or "").strip()
                frequency = int(item.get("frequency") or 0)
                aliases = "、".join(str(alias) for alias in (item.get("aliases") or []))
                lines.append(f"| {canonical_name} | {frequency} | {aliases} |")

            lines.append("")

        return "\n".join(lines).rstrip() + "\n"
