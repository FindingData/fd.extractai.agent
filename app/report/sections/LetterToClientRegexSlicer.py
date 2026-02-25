import re
from typing import Iterable, List, Optional

from app.report.context import ReportContext, ReportSection
from app.report.sections.base import SectionSlicer


class LetterToClientRegexSlicer(SectionSlicer):
    """
    用正则范围截取“致函”：
    - start_pattern: 起始锚点（包含）
    - end_pattern:   结束锚点（不包含，截到它前面）
    """

    def __init__(
        self,
        *,
        key: str = "letter_to_client",
        start_pattern: str = r"致\s*估\s*价\s*委\s*托\s*人\s*函[：:]?",
        end_pattern: str = r"目\s*录",
        flags: int = re.DOTALL | re.IGNORECASE,
        max_chars: int = 6000,              # 防止截太长
        fallback_chars: int = 600,
        enable_fallback: bool = True,
        take_first_only: bool = True,       # 多命中时只取第一个（多数报告够用）
    ) -> None:
        super().__init__(key=key)
        self.start_pattern = start_pattern
        self.end_pattern = end_pattern
        self.flags = flags
        self.max_chars = max_chars
        self.fallback_chars = fallback_chars
        self.enable_fallback = enable_fallback
        self.take_first_only = take_first_only

        # ✅ 与你旧逻辑等价：({start}.*?)(?={end})
        self._regex = re.compile(
            f"({self.start_pattern}.*?)(?={self.end_pattern})",
            self.flags,
        )

    def slice(self, context: ReportContext) -> Iterable[ReportSection]:
        md = context.ensure_markdown()

        matches = list(self._regex.finditer(md))
        sections: List[ReportSection] = []

        if matches:
            for idx, m in enumerate(matches, 1):
                text = (m.group(1) or "").strip()
                if not text:
                    continue
                if self.max_chars and len(text) > self.max_chars:
                    text = text[: self.max_chars]

                sections.append(
                    ReportSection(
                        key=self.key,
                        title=f"致函（regex#{idx}）",
                        text=text,
                        metadata={
                            "mode": "regex_range",
                            "start_pattern": self.start_pattern,
                            "end_pattern": self.end_pattern,
                            "span": [m.start(1), m.end(1)],
                            "truncated": len(m.group(1)) > len(text),
                        },
                    )
                )

                if self.take_first_only:
                    break

        # fallback：保持你当前框架风格（可选）
        if not sections and self.enable_fallback:
            snippet = (md or "")[: self.fallback_chars]
            if snippet.strip():
                sections.append(
                    ReportSection(
                        key=self.key,
                        title="致函（fallback）",
                        text=snippet,
                        metadata={"fallback": True, "fallback_chars": self.fallback_chars},
                    )
                )

        return sections