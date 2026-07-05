"""SenseNova (商汤) vision and chat providers."""

from __future__ import annotations

from typing import Any

from ....config.settings import AI_API_KEY, AI_TIMEOUT
from ..core.prompts import persisted_ai_settings
from ..core.registry import register_chat_provider, register_provider
from ...settings.api_keys import provider_api_key
from ...settings.provider_profiles import resolve_provider_profile_or_default
from ._chat import OpenAICompatibleChatProvider
from ._vision import OpenAICompatibleVisionTranscriber

_VISION_BASE_URL = "https://token.sensenova.cn/v1"
_VISION_DEFAULT_MODEL = "sensenova-6.7-flash-lite"


class SenseNovaVisionProvider(OpenAICompatibleVisionTranscriber):
    """商汤 SenseNova 6.7 Flash-Lite — 原生多模态，支持图像理解与 OCR。"""

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
        profile_matches = profile.provider == "sensenova"
        self.base_url = (
            base_url or (profile.base_url if profile_matches else "") or _VISION_BASE_URL
        ).rstrip("/")
        self.model = (
            model or (profile.model if profile_matches else "") or _VISION_DEFAULT_MODEL
        )
        self.api_key = (
            api_key or provider_api_key(persisted, "ai", profile.id) or AI_API_KEY
        )
        self.timeout = timeout
        self.dry_run = dry_run


class SenseNovaChatProvider(OpenAICompatibleChatProvider):
    """商汤 SenseNova DeepSeek-V4-Flash — 思考模式使用 ``reasoning_effort`` 字符串。"""

    def thinking_kwargs(self, enable_thinking: bool | None) -> dict[str, Any]:
        if enable_thinking is None:
            return {}
        return {"reasoning_effort": "none" if enable_thinking is False else "high"}


register_provider("sensenova", SenseNovaVisionProvider)
register_chat_provider("sensenova", SenseNovaChatProvider)
