from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

SliceMode = Literal[
    "by_heading",        # 标题分段（sectionize + bucket_by_targets）
    "by_regex_block",    # 正则找块（find_blocks_by_pattern）
    "by_table_after",    # 命中标题后向下抓 md table
    "by_window_after",   # 从锚点后截窗口
]

MissingPolicy = Literal["empty", "full", "raise"]

MergeStrategy = Literal[
    "replace",           # 整个 ruleset 替换
    "override_steps",    # 按 step.key 覆盖/新增（推荐默认）
    "append_steps",      # 直接追加 steps（不去重）
]


@dataclass
class SliceStep:
    key: str
    mode: SliceMode
    targets: List[str] = field(default_factory=list)
    within: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    missing: MissingPolicy = "empty"


@dataclass
class SliceRuleSet:
    name: str
    steps: List[SliceStep] = field(default_factory=list)
    defaults: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> Tuple[bool, List[str]]:
        """
        规则自检：尽量早发现配置问题
        """
        errors: List[str] = []
        if not self.name:
            errors.append("ruleset.name is required")

        seen_step_keys = set()
        for i, s in enumerate(self.steps):
            if not s.key:
                errors.append(f"steps[{i}].key is required")
            if s.key in seen_step_keys:
                errors.append(f"duplicate step.key: {s.key}")
            seen_step_keys.add(s.key)

            if s.mode not in ("by_heading", "by_regex_block", "by_table_after", "by_window_after"):
                errors.append(f"steps[{i}].mode invalid: {s.mode}")

            # mode 约束
            if s.mode in ("by_heading", "by_regex_block", "by_table_after") and not s.targets:
                errors.append(f"steps[{i}]({s.key}).targets required for mode={s.mode}")
            if s.mode == "by_window_after":
                if not s.targets or not s.targets[0]:
                    errors.append(f"steps[{i}]({s.key}).targets[0] anchor required for mode=by_window_after")

            if s.missing not in ("empty", "full", "raise"):
                errors.append(f"steps[{i}]({s.key}).missing invalid: {s.missing}")

        # within 引用检查：within 必须引用“前面已经产出的切片 key”
        produced_keys = set()
        for i, s in enumerate(self.steps):
            if s.within and s.within not in produced_keys:
                # 允许引用策略 slicer 产生的 key，因此这里只做 warn-like error：你可自行选择是否当 error
                # 这里仍加入 errors，逼你显式确认配置是否正确
                errors.append(
                    f"steps[{i}]({s.key}).within='{s.within}' not produced by previous steps; "
                    f"ensure it exists from strategy slicers or earlier rule steps."
                )
            produced_keys.add(s.key)

        return (len(errors) == 0), errors


def merge_rulesets(
    base: SliceRuleSet,
    override: SliceRuleSet,
    *,
    strategy: MergeStrategy = "override_steps",
    keep_base_name: bool = False,
) -> SliceRuleSet:
    """
    合并规则：
    - replace：直接用 override
    - append_steps：base.steps + override.steps
    - override_steps：按 step.key 覆盖（同 key 替换；新 key 追加）
    defaults：浅合并（override 覆盖 base）
    """
    if strategy == "replace":
        return override

    name = base.name if keep_base_name else (override.name or base.name)
    defaults = {**(base.defaults or {}), **(override.defaults or {})}

    if strategy == "append_steps":
        return SliceRuleSet(name=name, defaults=defaults, steps=[*(base.steps or []), *(override.steps or [])])

    # override_steps（推荐）
    base_map = {s.key: s for s in (base.steps or [])}
    out_steps: List[SliceStep] = []

    # 先按 base 原顺序输出（保证稳定）
    for s in base.steps or []:
        out_steps.append(base_map[s.key])

    # 覆盖/新增
    for os in override.steps or []:
        if os.key in base_map:
            # 替换同 key
            for i, s in enumerate(out_steps):
                if s.key == os.key:
                    out_steps[i] = os
                    break
        else:
            out_steps.append(os)

    return SliceRuleSet(name=name, defaults=defaults, steps=out_steps)