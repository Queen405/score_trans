from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LlmProviderKind = Literal["ocr", "ai", "assistant"]


@dataclass(frozen=True, slots=True)
class LlmProviderProfile:
    id: str
    label: str
    provider: str
    base_url: str
    model: str
    description: str = ""
    fallback_model: str = ""
