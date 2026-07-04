"""Alibaba DashScope (百炼) vision provider for AI transcription."""

from __future__ import annotations

from ..core.config import AI_API_KEY, AI_TIMEOUT
from ..core.prompts import persisted_ai_settings
from ..core.registry import register_provider
from ...settings.api_keys import provider_api_key
from ...settings.provider_profiles import resolve_provider_profile_or_default
from ._vision import OpenAICompatibleVisionTranscriber

_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-vl-max"


class DashScopeVisionProvider(OpenAICompatibleVisionTranscriber):
    """阿里云百炼 DashScope，支持 qwen-vl-max / qwen3-vl-plus 等视觉模型。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = AI_TIMEOUT,
        dry_run: bool = False,
    ) -> None:
        persisted = persisted_ai_settings()
        profile = resolve_provider_profile_or_default(
            "ai", persisted.get("ai_provider")
        )
        profile_matches = profile.provider == "dashscope"
        self.base_url = (
            base_url or (profile.base_url if profile_matches else "") or _BASE_URL
        ).rstrip("/")
        self.model = (
            model or (profile.model if profile_matches else "") or _DEFAULT_MODEL
        )
        self.api_key = (
            api_key or provider_api_key(persisted, "ai", profile.id) or AI_API_KEY
        )
        self.timeout = timeout
        self.dry_run = dry_run


register_provider("dashscope", DashScopeVisionProvider)
register_provider("aliyun", DashScopeVisionProvider)
