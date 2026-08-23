from __future__ import annotations

from ...settings.api_keys import provider_api_key
from ...settings.provider_profiles import resolve_provider_profile_or_default
from ..core.config import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_TIMEOUT,
)
from ..core.prompts import persisted_ai_settings
from ..core.registry import register_provider
from ._vision import OpenAICompatibleVisionTranscriber


class OpenAICompatibleVisionProvider(OpenAICompatibleVisionTranscriber):
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
        profile_matches = profile.provider == "openai_compatible"
        self.base_url = (
            base_url or (profile.base_url if profile_matches else "") or AI_BASE_URL
        ).rstrip("/")
        self.model = model or (profile.model if profile_matches else "") or AI_MODEL
        self.api_key = (
            api_key or provider_api_key(persisted, "ai", profile.id) or AI_API_KEY
        )
        self.timeout = timeout
        self.dry_run = dry_run
        # profile 未匹配本 provider 时不借用其 max_tokens（它属于别的模型）。
        self.max_tokens = profile.max_tokens if profile_matches else 0


register_provider("openai_compatible", OpenAICompatibleVisionProvider)
register_provider("siliconflow", OpenAICompatibleVisionProvider)
