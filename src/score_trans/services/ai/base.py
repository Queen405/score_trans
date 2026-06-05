# noqa: D100
from __future__ import annotations

# Compatibility re-exports for legacy imports.
# New code should import from score_trans.services.ai.core or .transcription.
from .core import (
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
    "VisionJianpuProvider",
    "VisionPageResult",
    "build_jianpu_prompt",
    "parse_vision_page_result",
    "looks_like_jianpu_text",
    "persisted_ai_settings",
    "_load_prompt_config",
    "_cfg_value",
]


