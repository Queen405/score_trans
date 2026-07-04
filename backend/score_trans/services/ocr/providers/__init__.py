from __future__ import annotations

from score_trans.services.settings.defaults import configured_settings_dao
from score_trans.services.settings.provider_profiles import (
    resolve_provider_profile_or_default,
)

from ..core.protocols import OCRProvider
from .dashscope import DashScopeOCRProvider
from .mock import MockOCRProvider
from .openai_compatible import OpenAICompatibleOCRProvider


def create_configured_ocr_provider() -> OCRProvider:
    settings = configured_settings_dao().get_all()
    profile = resolve_provider_profile_or_default("ocr", settings.get("ocr_provider"))
    base_url = settings.get("ocr_base_url") or profile.base_url
    model = settings.get("ocr_model") or profile.model
    if profile.provider == "dashscope":
        return DashScopeOCRProvider(
            base_url=base_url,
            model=model,
        )
    if profile.provider == "openai_compatible":
        return OpenAICompatibleOCRProvider(
            base_url=base_url,
            model=model,
            fallback_model=profile.fallback_model,
        )
    if profile.provider == "mock":
        return MockOCRProvider()
    raise ValueError(
        f"Unsupported OCR provider type {profile.provider!r} for profile {profile.id!r}"
    )


__all__ = [
    "DashScopeOCRProvider",
    "MockOCRProvider",
    "OpenAICompatibleOCRProvider",
    "create_configured_ocr_provider",
]
