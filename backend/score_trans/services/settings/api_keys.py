from __future__ import annotations

from collections.abc import Mapping

from score_trans.models.settings.provider_profiles import LlmProviderKind


def provider_api_key_name(provider_id: str) -> str:
    return f"{provider_id}_api_key"


def provider_api_key(
    settings: Mapping[str, str],
    kind: LlmProviderKind,
    provider_id: str,
) -> str:
    # 1. Provider-specific key (e.g. "xiaomi_mimo_v25_api_key")
    key = settings.get(provider_api_key_name(provider_id), "")
    if key:
        return key
    # 2. Generic kind key (e.g. "ai_api_key") — always try as fallback
    return settings.get(f"{kind}_api_key", "")
