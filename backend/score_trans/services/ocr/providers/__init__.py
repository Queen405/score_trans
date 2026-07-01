from __future__ import annotations

from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.services.settings.provider_profiles import (
    resolve_provider_profile_or_default,
)

from ..core.protocols import OCRProvider
from .dashscope import DashScopeOCRProvider
from .mock import MockOCRProvider
from .openai_compatible import OpenAICompatibleOCRProvider


def create_configured_ocr_provider() -> OCRProvider:
    settings = SettingsDao.default().get_all()
    profile = resolve_provider_profile_or_default("ocr", settings.get("ocr_provider"))
    if profile.provider == "dashscope":
        return DashScopeOCRProvider(
            base_url=profile.base_url,
            model=profile.model,
        )
    return OpenAICompatibleOCRProvider(
        base_url=profile.base_url,
        model=profile.model,
        fallback_model=profile.fallback_model,
    )


__all__ = [
    "DashScopeOCRProvider",
    "MockOCRProvider",
    "OpenAICompatibleOCRProvider",
    "create_configured_ocr_provider",
]
