from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.utils.markdown_utils import bucket_by_targets, sectionize


@dataclass
class ReportSection:
    """Normalized block of text that can be routed to extractors."""

    key: str
    title: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **extra: Any) -> "ReportSection":
        merged = {**self.metadata, **extra}
        return ReportSection(key=self.key, title=self.title, text=self.text, metadata=merged)


@dataclass
class ReportContext:
    """
    Holds lifecycle data for a report as it goes through convert -> slice -> extract -> eval.
    """

    source_path: Optional[Path] = None
    markdown_text: Optional[str] = None

    # ✅ 切片容器：key -> [ReportSection...]
    slices: Dict[str, List[ReportSection]] = field(default_factory=dict)

    metadata: Dict[str, Any] = field(default_factory=dict)

    def ensure_markdown(self) -> str:
        if not self.markdown_text:
            raise ValueError("Markdown content is required before slicing.")
        return self.markdown_text

    def set_markdown(self, markdown: str) -> None:
        self.markdown_text = markdown

    def set_metadata(self, **extra: Any) -> None:
        self.metadata.update(extra)

    # ============================================================
    # Slice helpers (关键：让 within 链式切片可用)
    # ============================================================

    def add_slice(self, section: Optional[ReportSection]) -> bool:
        """
        ✅ 写回一个切片到 ctx.slices
        - 返回 bool 表示是否成功写入（便于调试）
        - 忽略 None / 空 key
        """
        if section is None:
            return False
        key = (getattr(section, "key", None) or "").strip()
        if not key:
            return False

        self.slices.setdefault(key, []).append(section)

        # 可选调试：ctx.metadata["debug_slice"]=True 时打印
        if bool(self.metadata.get("debug_slice")):
            print(f"   🧾 [ctx.add_slice] key={key} now_count={len(self.slices.get(key) or [])}")

        return True

    def add_slices(self, sections: Sequence[ReportSection]) -> int:
        """批量写回切片，返回成功写入数量。"""
        n = 0
        for s in sections or []:
            if self.add_slice(s):
                n += 1
        return n

    def get_slice(self, key: str) -> Optional[ReportSection]:
        arr = self.slices.get(key) or []
        return arr[0] if arr else None

    def get_slices(self, key: str) -> List[ReportSection]:
        return list(self.slices.get(key) or [])

    def has_slice(self, key: str) -> bool:
        return bool(self.slices.get(key))

    def slice_keys(self) -> List[str]:
        return list(self.slices.keys())

    def slice_counts(self) -> Dict[str, int]:
        return {k: len(v or []) for k, v in (self.slices or {}).items()}

    def clear_slices(self) -> None:
        self.slices.clear()

    # ============================================================
    # Legacy config slicing (可保留)
    # ============================================================

    def slice_by_config(self, config: Dict[str, List[str]]) -> Dict[str, List[ReportSection]]:
        md_text = self.ensure_markdown()
        sections = sectionize(md_text)
        grouped = bucket_by_targets(sections, config)

        normalized: Dict[str, List[ReportSection]] = {}
        for key, raw_sections in grouped.items():
            normalized[key] = [
                ReportSection(
                    key=key,
                    title=raw["title"],
                    text=raw["content"],
                    metadata={"level": raw["level"]},
                )
                for raw in raw_sections
            ]
        return normalized

    def iter_slices(self) -> Iterable[ReportSection]:
        for arr in self.slices.values():
            for section in arr:
                yield section