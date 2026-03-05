from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class WordToMarkdownError(RuntimeError):
    pass


@dataclass(frozen=True)
class WordToMarkdownOptions:
    """
    预留：未来你可以加 libreoffice 路径、临时目录、是否保留图片、最大字符等参数。
    """
    pass


class WordToMarkdownConverter:
    """
    Word(doc/docx) -> Markdown 的包内统一入口。

    当前策略：
    1) 如果你已经把真实实现迁入本包：直接用包内实现（你后续把 _convert_impl 替换掉即可）
    2) 否则临时 fallback 到旧位置 app.utils.text_utils.convert_word_to_md
       （保证你现在的工程不被一次迁移搞崩）
    """

    def __init__(self, options: Optional[WordToMarkdownOptions] = None) -> None:
        self.options = options or WordToMarkdownOptions()

    def convert(self, source_path: str | Path) -> str:
        p = Path(source_path)
        if not p.exists():
            raise WordToMarkdownError(f"source file not found: {p}")

        # --- 先尝试包内实现（你后续把这里替换成真正实现） ---
        try:
            return self._convert_impl(p)
        except NotImplementedError:
            # --- fallback 到旧实现：迁移期间保证可跑 ---
            return self._fallback_convert(p)

    def _convert_impl(self, path: Path) -> str:
        """
        TODO：把你原先 app.utils.text_utils.convert_word_to_md 的真实实现复制到这里，
        或者在这里调用你未来的 MarkItDown/LibreOffice 管道。
        """
        raise NotImplementedError

    @staticmethod
    def _fallback_convert(path: Path) -> str:
        try:
            from app.utils.text_utils import convert_word_to_md as old_convert  # type: ignore
        except Exception as e:
            raise WordToMarkdownError(
                "convert_word_to_md is not implemented in fd_extractai_report yet, "
                "and fallback import app.utils.text_utils.convert_word_to_md failed."
            ) from e

        return old_convert(str(path))


# ---- 对外函数式 API：保持你原先调用习惯 ----
_default_converter = WordToMarkdownConverter()


def convert_word_to_md(source_path: str | Path) -> str:
    return _default_converter.convert(source_path)