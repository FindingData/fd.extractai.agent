from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence, Union

from fd_extractai_report.context import ReportContext, ReportSection
from fd_extractai_report.sections.base import SectionSlicer
from app.utils.markdown_utils import find_blocks_by_pattern

PatternLike = Union[str, re.Pattern]


class ValuationTablesSlicer(SectionSlicer):
    """Collect table-heavy sections for valuation extraction.

    策略：
    1) 依赖致函（letter_key）定位：
       - 先在致函文本里找表
       - 再在“致函锚点之后窗口”找表
    2) 仍找不到表 -> fallback 到致函内容（不是全文）
    3) 连致函都没有 -> 最后兜底全文
    """

    DEFAULT_TABLE_PATTERNS: List[re.Pattern] = [
        re.compile(r"估价结果一览表", re.I),
        re.compile(r"估价结果汇总表", re.I),
        re.compile(r"估价(对象|结果).*(表|列表)", re.I),
        re.compile(r"估价一览表", re.I),
        re.compile(r"valuation", re.I),
    ]

    def __init__(
        self,
        *,
        key: str = "valuation_tables",
        letter_key: str = "letter_to_client",
        table_patterns: Optional[Sequence[PatternLike]] = None,  # ✅ 外部可传入
        # 从全文里“致函之后”向后扩展的窗口长度（字符）
        search_after_letter_chars: int = 12000,
        # 表块仍然太大时可截断（防止喂模型过长）
        max_table_chars: int = 12000,
        # 未命中表时，fallback 回致函截取多少
        fallback_letter_chars: int = 6000,
        # 找不到锚点时是否仍然尝试在全文找表（可选）
        allow_fulltext_search_if_no_anchor: bool = False,
    ) -> None:
        super().__init__(key=key)
        self.letter_key = letter_key
        self.search_after_letter_chars = search_after_letter_chars
        self.max_table_chars = max_table_chars
        self.fallback_letter_chars = fallback_letter_chars
        self.allow_fulltext_search_if_no_anchor = allow_fulltext_search_if_no_anchor

        # ✅ 编译外部传入 patterns
        self.table_patterns: List[re.Pattern] = self._compile_patterns(
            table_patterns or self.DEFAULT_TABLE_PATTERNS
        )

    @staticmethod
    def _compile_patterns(patterns: Sequence[PatternLike]) -> List[re.Pattern]:
        compiled: List[re.Pattern] = []
        for p in patterns:
            if isinstance(p, re.Pattern):
                compiled.append(p)
            else:
                compiled.append(re.compile(p, re.I))
        return compiled

    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        full_text = context.ensure_markdown()
        aggregated: List[ReportSection] = []

        # 1) 拿到致函切片（可能多个）
        letter_slices = context.get_slices(self.letter_key) or []
        letter_text = "\n\n".join(s.text for s in letter_slices if s and s.text).strip()

        # 2) 优先：在致函文本里找表块
        if letter_text:
            aggregated.extend(self._find_tables(letter_text, scope="letter"))

        # 3) 次优：致函往后扩一个窗口，在窗口里找表（很多表不在致函内部）
        if not aggregated and letter_text:
            anchor = self._find_anchor_pos(full_text, letter_text)
            if anchor is not None:
                start = anchor
                end = min(len(full_text), start + self.search_after_letter_chars)
                window = full_text[start:end]
                aggregated.extend(
                    self._find_tables(window, scope="after_letter_window", span=[start, end])
                )
            elif self.allow_fulltext_search_if_no_anchor:
                # 可选兜底：锚点找不到时仍尝试全文匹配一次（谨慎启用）
                aggregated.extend(self._find_tables(full_text, scope="fulltext_no_anchor"))

        # 4) 如果还找不到表：fallback 回致函（不是全文）
        if not aggregated and letter_text:
            t = letter_text
            if self.fallback_letter_chars and len(t) > self.fallback_letter_chars:
                t = t[: self.fallback_letter_chars]
            aggregated.append(
                ReportSection(
                    key=self.key,
                    title="估价表（fallback->致函）",
                    text=t,
                    metadata={
                        "fallback": True,
                        "fallback_source": self.letter_key,
                        "patterns": [p.pattern for p in self.table_patterns],
                    },
                )
            )
            return aggregated

        # 5) 连致函都没有：最后兜底全文（极少情况）
        if not aggregated:
            aggregated.append(
                ReportSection(
                    key=self.key,
                    title="估价表（fallback->全文）",
                    text=full_text,
                    metadata={
                        "fallback": True,
                        "fallback_source": "__full__",
                        "patterns": [p.pattern for p in self.table_patterns],
                    },
                )
            )

        return aggregated

    def _looks_like_md_table(self, s: str) -> bool:
        if not s:
            return False
        if "| ---" in s or "|---" in s:
            return True
        lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
        pipe_lines = sum(1 for ln in lines if ln.startswith("|"))
        return pipe_lines >= 3

    def _grab_table_after_heading(self, text: str, heading: str, max_chars: int = 8000) -> str:
        pos = text.find(heading)
        if pos < 0:
            return ""
        tail = text[pos: pos + max_chars]
        lines = tail.splitlines()

        out = []
        in_table = False
        for ln in lines:
            if ln.strip() == "" and in_table:
                break
            out.append(ln)
            if ln.strip().startswith("|"):
                in_table = True
        return "\n".join(out).strip()

    def _find_tables(self, text: str, *, scope: str, span: Optional[List[int]] = None) -> List[ReportSection]:
        out: List[ReportSection] = []
        seen = set()

        for pattern in self.table_patterns:
            matches = find_blocks_by_pattern(text, pattern)
            for idx, match in enumerate(matches):
                title = match.get("title") or match.get("kind", "snippet")
                raw = (match.get("text") or "").strip()
                if not raw:
                    continue

                # ✅ 1) 如果只是标题段，尝试向下抓表
                expanded = raw
                if len(raw) <= 40 and ("表" in raw):
                    grabbed = self._grab_table_after_heading(text, raw, max_chars=min(self.max_table_chars, 8000))
                    if grabbed:
                        expanded = grabbed

                # ✅ 2) 过滤：优先保留“真的像表”的块
                # 如果 expanded 不是表，就先跳过（避免 “抵押价值” 这类噪声）
                if not self._looks_like_md_table(expanded):
                    continue

                truncated = False
                if self.max_table_chars and len(expanded) > self.max_table_chars:
                    expanded = expanded[: self.max_table_chars]
                    truncated = True

                # 去重：相同文本不重复塞
                key = (expanded[:200], pattern.pattern, scope)
                if key in seen:
                    continue
                seen.add(key)

                meta = {
                    "pattern": pattern.pattern,
                    "kind": match.get("kind"),
                    "match_index": idx,
                    "scope": scope,
                    "truncated": truncated,
                    "expanded": expanded != raw,
                }
                if span:
                    meta["span"] = span

                out.append(
                    ReportSection(
                        key=self.key,
                        title=title,
                        text=expanded,
                        metadata=meta,
                    )
                )
        return out

    @staticmethod
    def _find_anchor_pos(full_text: str, letter_text: str) -> Optional[int]:
        """
        尝试在全文中找到致函的起点。
        注意：因为致函可能经过清洗/截断，不一定能完全命中，所以只取前 N 字做锚。
        """
        if not full_text or not letter_text:
            return None
        anchor = letter_text[:200].strip()
        if not anchor:
            return None
        pos = full_text.find(anchor)
        return pos if pos >= 0 else None