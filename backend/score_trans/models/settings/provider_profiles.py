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
    # 输出 token 上限；0 表示未配置（回退到环境变量，再回退兼容默认值）。
    max_tokens: int = 0
