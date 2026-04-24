from __future__ import annotations

import importlib.util
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Any, Optional, Union

from markitdown import MarkItDown

from fd_extractai_report.settings import CONFIG, LLMConfig


ConverterSource = Union[bytes, str, Path]
_DOCX_OCR_ORDER_PATCHED = False

logger = logging.getLogger(__name__)


class OCRDependencyError(RuntimeError):
    pass


class OCRConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarkdownConvertOptions:
    soffice_path: str = "soffice"
    keep_converted_docx: bool = False
    strip: bool = True
    max_chars: int = 0
    timeout_sec: int = 120
    enable_ocr: Optional[bool] = None
    ocr_model_id: Optional[str] = None
    ocr_base_url: Optional[str] = None
    ocr_api_key: Optional[str] = None
    ocr_prompt: Optional[str] = None


class MarkdownFileConverter:
    def __init__(
        self,
        options: Optional[MarkdownConvertOptions] = None,
        *,
        llm_config: Optional[LLMConfig] = None,
    ) -> None:
        self.llm_config = llm_config or CONFIG
        self.opt = self._resolve_options(options)
        self.md = self._build_markitdown()

    def _resolve_options(
        self,
        options: Optional[MarkdownConvertOptions],
    ) -> MarkdownConvertOptions:
        default_options = MarkdownConvertOptions(
            enable_ocr=self.llm_config.enable_ocr,
            ocr_model_id=self.llm_config.ocr_model_id or self.llm_config.model_id,
            ocr_base_url=self.llm_config.ocr_base_url or self.llm_config.base_url,
            ocr_api_key=self.llm_config.ocr_api_key or self.llm_config.api_key,
            ocr_prompt=self.llm_config.ocr_prompt or None,
        )
        if options is None:
            return default_options

        resolved = options
        if resolved.enable_ocr is None:
            resolved = replace(resolved, enable_ocr=default_options.enable_ocr)
        if not resolved.ocr_model_id:
            resolved = replace(resolved, ocr_model_id=default_options.ocr_model_id)
        if not resolved.ocr_base_url:
            resolved = replace(resolved, ocr_base_url=default_options.ocr_base_url)
        if not resolved.ocr_api_key:
            resolved = replace(resolved, ocr_api_key=default_options.ocr_api_key)
        if not resolved.ocr_prompt:
            resolved = replace(resolved, ocr_prompt=default_options.ocr_prompt)
        return resolved

    def _build_markitdown(self) -> MarkItDown:
        if not self.opt.enable_ocr:
            return MarkItDown()

        self._ensure_ocr_dependencies()
        self._patch_docx_ocr_image_order()
        llm_client = self._build_ocr_client()

        kwargs: dict[str, Any] = {
            "enable_plugins": True,
            "llm_client": llm_client,
            "llm_model": self.opt.ocr_model_id,
        }
        if self.opt.ocr_prompt:
            kwargs["llm_prompt"] = self.opt.ocr_prompt

        logger.info("Initialize MarkItDown with OCR plugin enabled.")
        return MarkItDown(**kwargs)

    def _patch_docx_ocr_image_order(self) -> None:
        global _DOCX_OCR_ORDER_PATCHED

        if _DOCX_OCR_ORDER_PATCHED:
            return

        try:
            from docx import Document
            from docx.oxml.ns import qn
            from markitdown_ocr._docx_converter_with_ocr import DocxConverterWithOCR
        except ImportError:
            return

        def _extract_and_ocr_images_in_document_order(self, file_stream: Any, ocr_service: Any) -> dict[str, str]:
            ocr_map: dict[str, str] = {}

            try:
                file_stream.seek(0)
                doc = Document(file_stream)
                ordered_rel_ids: list[str] = []

                for blip in doc.part.element.xpath(".//a:blip"):
                    rel_id = blip.get(qn("r:embed"))
                    if rel_id and rel_id not in ordered_rel_ids:
                        ordered_rel_ids.append(rel_id)

                for rel_id in ordered_rel_ids:
                    rel = doc.part.rels.get(rel_id)
                    target_ref = getattr(rel, "target_ref", "") if rel is not None else ""
                    if rel is None or "image" not in target_ref.lower():
                        continue

                    try:
                        image_stream = BytesIO(rel.target_part.blob)
                        ocr_result = ocr_service.extract_text(image_stream)
                    except Exception as exc:
                        logger.warning(
                            "DOCX OCR failed for image %s: %s",
                            target_ref,
                            exc,
                        )
                        continue

                    text = (ocr_result.text or "").strip()
                    if text:
                        ocr_map[rel_id] = text
                    elif getattr(ocr_result, "error", None):
                        logger.warning(
                            "DOCX OCR returned empty text for image %s: %s",
                            target_ref,
                            ocr_result.error,
                        )
            except Exception as exc:
                logger.warning("Failed to extract DOCX images in document order: %s", exc)

            return ocr_map

        DocxConverterWithOCR._extract_and_ocr_images = _extract_and_ocr_images_in_document_order
        _DOCX_OCR_ORDER_PATCHED = True

    def _ensure_ocr_dependencies(self) -> None:
        if importlib.util.find_spec("markitdown_ocr") is None:
            raise OCRDependencyError(
                "OCR 已启用，但未安装 `markitdown-ocr`。请先安装该依赖。"
            )
        if importlib.util.find_spec("openai") is None:
            raise OCRDependencyError(
                "OCR 已启用，但未安装 `openai`。请先安装该依赖。"
            )

    def _build_ocr_client(self) -> Any:
        if not self.opt.ocr_model_id:
            raise OCRConfigurationError("OCR 已启用，但缺少 OCR 模型配置。")
        if not self.opt.ocr_base_url:
            raise OCRConfigurationError("OCR 已启用，但缺少 OCR base URL 配置。")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OCRDependencyError(
                "OCR 已启用，但当前环境无法导入 `openai`。"
            ) from exc

        return OpenAI(
            base_url=self.opt.ocr_base_url,
            api_key=self.opt.ocr_api_key or "EMPTY",
            timeout=self.llm_config.timeout,
        )

    def convert(self, source: ConverterSource, *, filename: str | None = None) -> str:
        if isinstance(source, (str, Path)):
            return self._convert_path(Path(source))

        if isinstance(source, (bytes, bytearray)):
            return self._convert_bytes(bytes(source), filename=filename)

        raise TypeError(f"Unsupported source type: {type(source)}")

    def _convert_path(self, path: Path) -> str:
        if not path.exists():
            raise FileNotFoundError(path)

        suffix = path.suffix.lower()
        if suffix == ".doc":
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_p = Path(tmpdir)
                tmp_doc = tmpdir_p / path.name
                shutil.copy2(path, tmp_doc)

                docx = self._convert_doc_to_docx(tmp_doc, outdir=tmpdir_p)
                text = self._markitdown_file(docx)

                if self.opt.keep_converted_docx:
                    keep_path = path.with_suffix(".__converted__.docx")
                    shutil.copy2(docx, keep_path)

                return self._post(text)

        text = self._markitdown_file(path)
        return self._post(text)

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

        bio = BytesIO(file_bytes)
        result = self.md.convert_stream(bio, file_extension=suffix or None)
        return self._post(self._extract_text(result))

    def _markitdown_file(self, path: Path) -> str:
        result = self.md.convert(str(path))
        return self._extract_text(result)

    @staticmethod
    def _extract_text(result: Any) -> str:
        return getattr(result, "markdown", None) or getattr(result, "text_content", None) or ""

    def _post(self, text: str) -> str:
        if self.opt.strip:
            text = (text or "").strip()
        if self.opt.max_chars and len(text) > self.opt.max_chars:
            text = text[: self.opt.max_chars]
        return text

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
