from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Literal, Optional, Tuple


# =========================
# mode constants
# =========================
MODE_BY_HEADING = "by_heading"
MODE_BY_REGEX_BLOCK = "by_regex_block"
MODE_BY_TABLE_AFTER = "by_table_after"
MODE_BY_WINDOW_AFTER = "by_window_after"
MODE_BY_REGEX_BETWEEN = "by_regex_between"
MODE_BY_SEGMENT_TABLES = "by_segment_tables"

ALL_SLICE_MODES = {
    MODE_BY_HEADING,
    MODE_BY_REGEX_BLOCK,
    MODE_BY_TABLE_AFTER,
    MODE_BY_WINDOW_AFTER,
    MODE_BY_REGEX_BETWEEN,
    MODE_BY_SEGMENT_TABLES,
}


SliceMode = Literal[
    "by_heading",         # 标题分段（sectionize + bucket_by_targets）
    "by_regex_block",     # 正则找块（find_blocks_by_pattern）
    "by_table_after",     # 命中标题后向下抓 md table
    "by_window_after",    # 从锚点后截窗口
    "by_regex_between",   # 起止锚点之间截取
    "by_segment_tables",  # 段内表格抽取
]

MissingPolicy = Literal["empty", "full", "raise"]

MergeStrategy = Literal[
    "replace",           # 整个 ruleset 替换
    "override_steps",    # 按 step.key 覆盖/新增（推荐默认）
    "append_steps",      # 直接追加 steps（不去重）
]


# =========================
# helpers
# =========================
def _is_non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _is_non_empty_str_list(v: Any) -> bool:
    return isinstance(v, list) and any(_is_non_empty_str(x) for x in v)


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


# =========================
# schema
# =========================
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

        if not self.name or not self.name.strip():
            errors.append("ruleset.name is required")

        seen_step_keys = set()
        produced_keys = set()

        for i, s in enumerate(self.steps):
            step_tag = f"steps[{i}]({s.key or '?'})"

            # ---- key ----
            if not s.key or not s.key.strip():
                errors.append(f"steps[{i}].key is required")
            elif s.key in seen_step_keys:
                errors.append(f"duplicate step.key: {s.key}")
            else:
                seen_step_keys.add(s.key)

            # ---- mode ----
            if s.mode not in ALL_SLICE_MODES:
                errors.append(f"steps[{i}].mode invalid: {s.mode}")
                # mode 都不合法了，后续 mode-specific 校验意义不大
                produced_keys.add(s.key)
                continue

            # ---- missing ----
            if s.missing not in ("empty", "full", "raise"):
                errors.append(f"{step_tag}.missing invalid: {s.missing}")

            # ---- within 引用检查 ----
            if s.within:
                if not _is_non_empty_str(s.within):
                    errors.append(f"{step_tag}.within must be non-empty string")
                elif s.within not in produced_keys:
                    errors.append(
                        f"{step_tag}.within='{s.within}' not produced by previous steps; "
                        f"ensure it exists from earlier rule steps or preloaded slices."
                    )

            # ---- 通用 targets 检查 ----
            if s.mode in {
                MODE_BY_HEADING,
                MODE_BY_REGEX_BLOCK,
                MODE_BY_TABLE_AFTER,
                MODE_BY_WINDOW_AFTER,
                MODE_BY_REGEX_BETWEEN,
                MODE_BY_SEGMENT_TABLES,
            }:
                if not _is_non_empty_str_list(s.targets):
                    errors.append(f"{step_tag}.targets required for mode={s.mode}")

            # ---- mode-specific 校验 ----
            p = s.params or {}

            if s.mode == MODE_BY_WINDOW_AFTER:
                # 至少要有 anchor
                if not _is_non_empty_str_list(s.targets):
                    errors.append(f"{step_tag}.targets[0] anchor required for mode=by_window_after")

                window_chars = p.get("window_chars")
                if window_chars is not None and _as_int(window_chars, -1) <= 0:
                    errors.append(f"{step_tag}.params.window_chars must be > 0")

                anchor_pick = p.get("anchor_pick")
                if anchor_pick is not None and anchor_pick not in ("earliest", "priority"):
                    errors.append(f"{step_tag}.params.anchor_pick invalid: {anchor_pick}")

                anchor_regex = p.get("anchor_regex")
                if anchor_regex is not None and not isinstance(anchor_regex, bool):
                    errors.append(f"{step_tag}.params.anchor_regex must be bool")

            elif s.mode == MODE_BY_REGEX_BETWEEN:
                # start anchors 在 targets，end anchors 在 params["ends"]
                ends = p.get("ends")
                if not _is_non_empty_str_list(ends):
                    errors.append(f"{step_tag}.params.ends required for mode=by_regex_between")

                pick = p.get("pick")
                if pick is not None and pick not in ("earliest", "priority"):
                    errors.append(f"{step_tag}.params.pick invalid: {pick}")

                include_start = p.get("include_start")
                if include_start is not None and not isinstance(include_start, bool):
                    errors.append(f"{step_tag}.params.include_start must be bool")

                include_end = p.get("include_end")
                if include_end is not None and not isinstance(include_end, bool):
                    errors.append(f"{step_tag}.params.include_end must be bool")

                fallback_end_chars = p.get("fallback_end_chars")
                if fallback_end_chars is not None and _as_int(fallback_end_chars, -1) < 0:
                    errors.append(f"{step_tag}.params.fallback_end_chars must be >= 0")

                loose_space = p.get("loose_space")
                if loose_space is not None and not isinstance(loose_space, bool):
                    errors.append(f"{step_tag}.params.loose_space must be bool")

                skip_if_line_matches = p.get("skip_if_line_matches")
                if skip_if_line_matches is not None and not isinstance(skip_if_line_matches, list):
                    errors.append(f"{step_tag}.params.skip_if_line_matches must be list[str]")

            elif s.mode == MODE_BY_TABLE_AFTER:
                max_table_chars = p.get("max_table_chars")
                if max_table_chars is not None and _as_int(max_table_chars, -1) <= 0:
                    errors.append(f"{step_tag}.params.max_table_chars must be > 0")

                min_table_rows = p.get("min_table_rows")
                if min_table_rows is not None and _as_int(min_table_rows, -1) <= 0:
                    errors.append(f"{step_tag}.params.min_table_rows must be > 0")

            elif s.mode == MODE_BY_SEGMENT_TABLES:
                max_table_chars = p.get("max_table_chars")
                if max_table_chars is not None and _as_int(max_table_chars, -1) <= 0:
                    errors.append(f"{step_tag}.params.max_table_chars must be > 0")

                min_table_rows = p.get("min_table_rows")
                if min_table_rows is not None and _as_int(min_table_rows, -1) <= 0:
                    errors.append(f"{step_tag}.params.min_table_rows must be > 0")

                max_hits_per_pattern = p.get("max_hits_per_pattern")
                if max_hits_per_pattern is not None and _as_int(max_hits_per_pattern, -1) < 0:
                    errors.append(f"{step_tag}.params.max_hits_per_pattern must be >= 0")

            elif s.mode == MODE_BY_HEADING:
                # 这里可以暂时不加更多限制，保留宽松
                pass

            elif s.mode == MODE_BY_REGEX_BLOCK:
                # targets 作为 regex 列表，先只要求非空
                pass

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
        return SliceRuleSet(
            name=name,
            defaults=defaults,
            steps=[*(base.steps or []), *(override.steps or [])],
        )

    if strategy != "override_steps":
        raise ValueError(f"Unsupported merge strategy: {strategy}")

    base_steps = list(base.steps or [])
    override_steps = list(override.steps or [])

    override_map = {s.key: s for s in override_steps if s.key}
    out_steps: List[SliceStep] = []

    # 先保持 base 原顺序；若 override 同 key，则替换
    for s in base_steps:
        out_steps.append(override_map.pop(s.key, s))

    # 再追加 override 中新增的 step
    for s in override_steps:
        if s.key in {x.key for x in out_steps}:
            continue
        out_steps.append(s)

    return SliceRuleSet(
        name=name,
        defaults=defaults,
        steps=out_steps,
    )