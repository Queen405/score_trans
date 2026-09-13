from __future__ import annotations

import json

from ...dao.settings.settings_dao import SettingsDao
from ...models.common.paths import CONFIG_DIR

_BASELINE_PATH = CONFIG_DIR / "published_defaults.json"
_SUPPORTED_VERSION = 1

_BACKEND_STRING_KEYS: tuple[str, ...] = (
    "audiveris_max_heap",
    "audiveris_max_pixel_count",
    "audiveris_auto_upscale",
    "audiveris_min_image_edge",
    "target_key",
    "accidental_mode",
    "polyphony_mode",
    "measure_number_mode",
    "show_measure_numbers",
    "jianpu_syntax_highlight",
    "jianpu_measure_duration_check",
    "jianpu_content_scale_percent",
    "jianpu_system_gap_percent",
    "jianpu_short_note_gap_percent",
    "jianpu_beat_gap_percent",
    "enable_omr_ocr",
    "output_dir",
    "jianpu_auto_transpose",
)


def _load_published_defaults() -> dict:
    path = _BASELINE_PATH
    if not path.is_file():
        raise ValueError(
            f"published_defaults.json not found at {path}; "
            "the application cannot determine installation defaults."
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"published_defaults.json is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TypeError("published_defaults.json must be a JSON object")
    version = payload.get("version")
    if version != _SUPPORTED_VERSION:
        raise ValueError(
            f"published_defaults.json version {version!r} is unsupported; "
            f"expected version {_SUPPORTED_VERSION}."
        )
    return payload


def _require_str(section: dict, field: str, context: str) -> str:
    value = section.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"published_defaults.json {context}.{field} must be a non-empty string"
        )
    return value


def _require_backend_str(section: dict, field: str) -> str:
    value = section.get(field)
    if not isinstance(value, str):
        raise TypeError(f"published_defaults.json backend.{field} must be a string")
    return value


def settings_defaults() -> dict[str, str]:
    payload = _load_published_defaults()
    backend = payload.get("backend")
    if not isinstance(backend, dict):
        raise TypeError("published_defaults.json must contain a 'backend' object")
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        raise TypeError("published_defaults.json must contain a 'providers' object")

    defaults: dict[str, str] = {}

    for key in _BACKEND_STRING_KEYS:
        defaults[key] = _require_backend_str(backend, key)

    for kind in ("ocr", "ai", "assistant"):
        section = providers.get(kind)
        if not isinstance(section, dict):
            raise TypeError(
                f"published_defaults.json providers.{kind} must be an object"
            )
        defaults[f"{kind}_provider"] = _require_str(
            section, "provider", f"providers.{kind}"
        )
        defaults[f"{kind}_base_url"] = _require_str(
            section, "base_url", f"providers.{kind}"
        )
        defaults[f"{kind}_model"] = _require_str(section, "model", f"providers.{kind}")

    ocr_section = providers["ocr"]
    defaults["ocr_fallback_model"] = _require_str(
        ocr_section, "fallback_model", "providers.ocr"
    )

    # Paths: always empty seeds — auto-resolution handles them at runtime
    # via _resolve_existing_path / _default_* in SettingsService.
    defaults["audiveris_path"] = ""
    defaults["java_home"] = ""

    # API keys: always empty seeds — never inherit from environment.
    # OCR providers fall back to OCR_API_KEY env at runtime; AI/assistant
    # providers already fall back to AI_API_KEY / ASSISTANT_API_KEY env.
    defaults["ocr_api_key"] = ""
    defaults["ai_api_key"] = ""
    defaults["assistant_api_key"] = ""

    return defaults


def configured_settings_dao() -> SettingsDao:
    return SettingsDao.default(settings_defaults())
