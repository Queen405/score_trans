from __future__ import annotations

import json
from typing import Any

from score_trans.config.settings import (
    AI_PROVIDER,
    AI_PROVIDER_PROFILES,
    ASSISTANT_PROVIDER,
    ASSISTANT_PROVIDER_PROFILES,
    OCR_PROVIDER,
    OCR_PROVIDER_PROFILES,
)
from score_trans.models.settings.provider_profiles import (
    LlmProviderKind,
    LlmProviderProfile,
)

_PROFILE_ENV_NAMES: dict[LlmProviderKind, str] = {
    "ocr": "SCORE_TRANS_OCR_PROVIDER_PROFILES",
    "ai": "SCORE_TRANS_AI_PROVIDER_PROFILES",
    "assistant": "SCORE_TRANS_ASSISTANT_PROVIDER_PROFILES",
}
_KIND_LABELS: dict[LlmProviderKind, str] = {
    "ocr": "OCR",
    "ai": "AI 视觉转写",
    "assistant": "工作台 AI 助手",
}


def _parse_profiles(env_name: str, raw: str) -> tuple[LlmProviderProfile, ...]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{env_name} must be a JSON array of provider profiles"
        ) from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{env_name} must be a non-empty JSON array")

    profiles = tuple(_parse_profile(env_name, item) for item in payload)
    ids = [profile.id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{env_name} contains duplicate provider ids")
    return profiles


def _parse_profile(env_name: str, item: Any) -> LlmProviderProfile:
    if not isinstance(item, dict):
        raise ValueError(f"{env_name} entries must be JSON objects")
    required = ("id", "label", "provider", "base_url", "model")
    values: dict[str, str] = {}
    for key in required:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{env_name} entries require non-empty string field {key!r}"
            )
        values[key] = value.strip()
    return LlmProviderProfile(
        id=values["id"],
        label=values["label"],
        provider=values["provider"],
        base_url=values["base_url"].rstrip("/"),
        model=values["model"],
        description=_optional_string(item, "description"),
        fallback_model=_optional_string(item, "fallback_model"),
        max_tokens=_optional_positive_int(env_name, item, "max_tokens"),
    )


def _optional_string(item: dict[str, Any], key: str) -> str:
    value = item.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"provider profile field {key!r} must be a string")
    return value.strip()


def _optional_positive_int(env_name: str, item: dict[str, Any], key: str) -> int:
    """Parse an optional positive integer profile field; 0 means unset."""
    if key not in item or item[key] is None:
        return 0
    value = item[key]
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            f"{env_name} provider profile field {key!r} must be a positive integer"
        )
    return value


_PROFILES: dict[LlmProviderKind, tuple[LlmProviderProfile, ...]] = {
    "ocr": _parse_profiles("SCORE_TRANS_OCR_PROVIDER_PROFILES", OCR_PROVIDER_PROFILES),
    "ai": _parse_profiles("SCORE_TRANS_AI_PROVIDER_PROFILES", AI_PROVIDER_PROFILES),
    "assistant": _parse_profiles(
        "SCORE_TRANS_ASSISTANT_PROVIDER_PROFILES",
        ASSISTANT_PROVIDER_PROFILES,
    ),
}
_DEFAULTS: dict[LlmProviderKind, str] = {
    "ocr": OCR_PROVIDER,
    "ai": AI_PROVIDER,
    "assistant": ASSISTANT_PROVIDER,
}

for _kind, _default_id in _DEFAULTS.items():
    if _default_id not in {profile.id for profile in _PROFILES[_kind]}:
        env_name = {
            "ocr": "SCORE_TRANS_OCR_PROVIDER",
            "ai": "SCORE_TRANS_AI_PROVIDER",
            "assistant": "SCORE_TRANS_ASSISTANT_PROVIDER",
        }[_kind]
        raise ValueError(
            f"{env_name}={_default_id!r} must match an id in {_PROFILE_ENV_NAMES[_kind]}"
        )


def provider_profiles(kind: LlmProviderKind) -> tuple[LlmProviderProfile, ...]:
    return _PROFILES[kind]


def resolve_provider_profile(
    kind: LlmProviderKind,
    provider_id: str | None,
) -> LlmProviderProfile:
    resolved = (provider_id or _DEFAULTS[kind]).strip()
    for profile in _PROFILES[kind]:
        if profile.id == resolved:
            return profile
    available = ", ".join(profile.id for profile in _PROFILES[kind])
    raise ValueError(
        f"未知{_KIND_LABELS[kind]} provider：{resolved}。可选：{available}"
    )


def resolve_provider_profile_or_default(
    kind: LlmProviderKind,
    provider_id: str | None,
) -> LlmProviderProfile:
    try:
        return resolve_provider_profile(kind, provider_id)
    except ValueError:
        return resolve_provider_profile(kind, _DEFAULTS[kind])
