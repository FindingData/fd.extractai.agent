from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class LLMConfig:
    model_id: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434/v1"
    api_key: str = ""
    timeout: int = 600
    options: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            model_id=os.getenv("LLM_MODEL_ID", "qwen3:8b"),
            base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            timeout=int(os.getenv("LLM_TIMEOUT", "600")),
        )

    def with_options(self, **kwargs: Any) -> "LLMConfig":
        merged = dict(self.options)
        merged.update(kwargs)
        return LLMConfig(
            model_id=self.model_id,
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            options=merged,
        )

CONFIG = LLMConfig.from_env()