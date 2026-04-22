from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMConfig:
    model_id: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434/v1"
    api_key: str = ""
    timeout: int = 600
    enable_ocr: bool = False
    ocr_model_id: str = ""
    ocr_base_url: str = ""
    ocr_api_key: str = ""
    ocr_prompt: str = ""
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            model_id=os.getenv("LLM_MODEL_ID", "qwen3:8b"),
            base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            timeout=int(os.getenv("LLM_TIMEOUT", "600")),
            enable_ocr=_env_bool("LLM_ENABLE_OCR", False),
            ocr_model_id=os.getenv("LLM_OCR_MODEL_ID", ""),
            ocr_base_url=os.getenv("LLM_OCR_BASE_URL", ""),
            ocr_api_key=os.getenv("LLM_OCR_API_KEY", ""),
            ocr_prompt=os.getenv("LLM_OCR_PROMPT", ""),
        )

    def with_options(self, **kwargs: Any) -> "LLMConfig":
        merged = dict(self.options)
        merged.update(kwargs)
        return LLMConfig(
            model_id=self.model_id,
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            enable_ocr=self.enable_ocr,
            ocr_model_id=self.ocr_model_id,
            ocr_base_url=self.ocr_base_url,
            ocr_api_key=self.ocr_api_key,
            ocr_prompt=self.ocr_prompt,
            options=merged,
        )


CONFIG = LLMConfig.from_env()
