from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional, Union
import shutil
import subprocess
import tempfile

from markitdown import MarkItDown


ConverterSource = Union[bytes, str, Path]


@dataclass(frozen=True)
class MarkdownConvertOptions:
    soffice_path: str = "soffice"   # LibreOffice 命令
    keep_converted_docx: bool = False  # 调试用：是否保留生成的 docx
    strip: bool = True
    max_chars: int = 0              # 0 表示不截断
    timeout_sec: int = 120          # 防止 soffice 卡死


class MarkdownFileConverter:
    def __init__(self, options: Optional[MarkdownConvertOptions] = None):
        self.opt = options or MarkdownConvertOptions()
        self.md = MarkItDown()

    def convert(self, source: ConverterSource, *, filename: str | None = None) -> str:
        """自动识别输入类型：Path/str/bytes -> Markdown"""
        if isinstance(source, (str, Path)):
            return self._convert_path(Path(source))

        if isinstance(source, (bytes, bytearray)):
            return self._convert_bytes(bytes(source), filename=filename)

        raise TypeError(f"Unsupported source type: {type(source)}")

    # ==========================
    # path 转换
    # ==========================
    def _convert_path(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(path)

        suffix = path.suffix.lower()

        if suffix == ".doc":
            # ✅ 用临时目录转换，避免在原目录生成同名 docx 污染/并发冲突
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_p = Path(tmpdir)
                tmp_doc = tmpdir_p / path.name
                shutil.copy2(path, tmp_doc)

                docx = self._convert_doc_to_docx(tmp_doc, outdir=tmpdir_p)
                text = self._markitdown_file(docx)

                if self.opt.keep_converted_docx:
                    # 需要保留就复制回原目录旁边（不覆盖）
                    keep_path = path.with_suffix(".__converted__.docx")
                    shutil.copy2(docx, keep_path)

                return self._post(text)

        # 其他格式直接交给 MarkItDown
        text = self._markitdown_file(path)
        return self._post(text)

    # ==========================
    # bytes 转换
    # ==========================
    def _convert_bytes(self, file_bytes: bytes, *, filename: str | None = None) -> str:
        if not file_bytes:
            return ""

        suffix = Path(filename).suffix.lower() if filename else ""

        if suffix == ".doc":
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_p = Path(tmpdir)
                tmp_doc = tmpdir_p / "input.doc"
                tmp_doc.write_bytes(file_bytes)

                docx = self._convert_doc_to_docx(tmp_doc, outdir=tmpdir_p)
                text = self._markitdown_file(docx)

                if self.opt.keep_converted_docx:
                    keep_path = tmpdir_p / "input.__converted__.docx"
                    shutil.copy2(docx, keep_path)

                return self._post(text)

        # 非 doc：直接 stream
        bio = BytesIO(file_bytes)
        result = self.md.convert_stream(bio)
        text = getattr(result, "markdown", None) or getattr(result, "text_content", None) or ""
        return self._post(text)

    # ==========================
    # MarkItDown helpers
    # ==========================
    def _markitdown_file(self, path: Path) -> str:
        result = self.md.convert(str(path))
        return getattr(result, "markdown", None) or getattr(result, "text_content", None) or ""

    def _post(self, text: str) -> str:
        if self.opt.strip:
            text = (text or "").strip()
        if self.opt.max_chars and len(text) > self.opt.max_chars:
            text = text[: self.opt.max_chars]
        return text

    # ==========================
    # doc -> docx
    # ==========================
    def _convert_doc_to_docx(self, path_obj: Path, *, outdir: Path) -> Path:
        cmd = [
            self.opt.soffice_path,
            "--headless",
            "--convert-to",
            "docx",
            "--outdir",
            str(outdir),
            str(path_obj),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.opt.timeout_sec,
        )

        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice 转换失败: {result.stderr or result.stdout}")

        generated = outdir / path_obj.with_suffix(".docx").name
        if not generated.exists():
            raise FileNotFoundError(f"LibreOffice 未生成 docx 文件: {generated}")

        return generated