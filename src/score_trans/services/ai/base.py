# noqa: D100
from __future__ import annotations

# Compatibility re-exports for legacy imports.
# New code should import from score_trans.services.ai.core or .transcription.
from .core import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_SYSTEM_MSG,
    AI_TEMPERATURE,
    AI_TIMEOUT,
    VisionJianpuProvider,
    VisionPageResult,
    _cfg_value,
    _load_prompt_config,
    build_jianpu_prompt,
    looks_like_jianpu_text,
    parse_vision_page_result,
    persisted_ai_settings,
)

__all__ = [
    "AI_API_KEY",
    "AI_BASE_URL",
    "AI_MODEL",
    "AI_SYSTEM_MSG",
    "AI_TEMPERATURE",
    "AI_TIMEOUT",
    "VisionJianpuProvider",
    "VisionPageResult",
    "build_jianpu_prompt",
    "parse_vision_page_result",
    "looks_like_jianpu_text",
    "persisted_ai_settings",
    "_load_prompt_config",
    "_cfg_value",
]


