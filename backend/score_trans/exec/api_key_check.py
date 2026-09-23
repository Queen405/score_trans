from __future__ import annotations

from score_trans.config.settings import AI_API_KEY, OCR_API_KEY
from score_trans.models.common.errors import AITranscriptionError, OCRError
from score_trans.services.ai.core.prompts import persisted_ai_settings
from score_trans.services.ocr.core.utils import persisted_ocr_settings
from score_trans.services.settings.api_keys import provider_api_key
from score_trans.services.settings.provider_profiles import (
    resolve_provider_profile_or_default,
)


def ensure_ocr_api_key_or_raise() -> None:
    """Raise ``OCRError`` when the configured OCR provider has no API key.

    Mirrors the key resolution in ``OpenAICompatibleOCRProvider`` /
    ``DashScopeOCRProvider`` so callers can preflight before scheduling a
    background task. The mock provider is exempted.
    """
    persisted = persisted_ocr_settings()
    profile = resolve_provider_profile_or_default("ocr", persisted.get("ocr_provider"))
    if profile.provider == "mock":
        return
    key = provider_api_key(persisted, "ocr", profile.id) or OCR_API_KEY
    if not key:
        raise OCRError("OCR API key not configured. Set it in Settings.")


def ensure_ai_api_key_or_raise() -> None:
    """Raise ``AITranscriptionError`` when the configured AI provider has no key.

    Mirrors the key resolution in the vision transcriber providers so callers
    can preflight before scheduling a background task.
    """
    persisted = persisted_ai_settings()
    profile = resolve_provider_profile_or_default("ai", persisted.get("ai_provider"))
    key = provider_api_key(persisted, "ai", profile.id) or AI_API_KEY
    if not key:
        raise AITranscriptionError("AI API key not configured. Set it in Settings.")
