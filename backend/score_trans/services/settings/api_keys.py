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
    key = settings.get(provider_api_key_name(provider_id), "")
    if key:
        return key
    saved_provider_id = settings.get(f"{kind}_provider", "")
    if not saved_provider_id or saved_provider_id == provider_id:
        return settings.get(f"{kind}_api_key", "")
    return ""
