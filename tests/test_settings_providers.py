from __future__ import annotations

import pytest

from score_trans.api.app import create_app
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.settings.actions import SettingsActions
from score_trans.models.settings.schemas import SettingsUpdateRequest
from score_trans.services.settings.provider_profiles import provider_profiles, resolve_provider_profile
from score_trans.services.settings.settings_service import SettingsService


def test_settings_update_schema_only_accepts_provider_ids() -> None:
    schema = create_app().openapi()["components"]["schemas"]["SettingsUpdateRequest"]
    properties = schema["properties"]

    assert "ocr_provider" in properties
    assert "ai_provider" in properties
    assert "assistant_provider" in properties
    assert "ocr_base_url" not in properties
    assert "ocr_model" not in properties
    assert "ai_base_url" not in properties
    assert "ai_model" not in properties
    assert "assistant_base_url" not in properties
    assert "assistant_model" not in properties


def test_settings_provider_update_resolves_fixed_profiles(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    actions = SettingsActions(SettingsService(dao))

    response = actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider="dashscope_qwen_vl_ocr",
            ai_provider="xiaomi_mimo_v25",
            assistant_provider="dashscope_qwen_plus",
        )
    )
    ocr_profile = resolve_provider_profile("ocr", "dashscope_qwen_vl_ocr")
    ai_profile = resolve_provider_profile("ai", "xiaomi_mimo_v25")

    assert response.ocr_provider == "dashscope_qwen_vl_ocr"
    assert response.ocr_base_url == ocr_profile.base_url
    assert response.ocr_model == ocr_profile.model
    assert response.ai_provider == "xiaomi_mimo_v25"
    assert response.ai_base_url == ai_profile.base_url
    assert response.ai_model == ai_profile.model
    assert response.assistant_provider == "dashscope_qwen_plus"
    assert response.assistant_model == "qwen-plus"
    assert dao.get("ocr_base_url") == ocr_profile.base_url
    assert dao.get("ai_model") == ai_profile.model
    assert dao.get("assistant_model") == "qwen-plus"


def test_settings_rejects_unknown_provider(tmp_path) -> None:
    actions = SettingsActions(SettingsService(SettingsDao(tmp_path / "settings.db")))

    with pytest.raises(ValueError, match="未知OCR provider"):
        actions.update_settings(SettingsUpdateRequest(ocr_provider="custom_model"))


def test_settings_saves_api_keys_per_provider(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("ocr_api_key", "")
    actions = SettingsActions(SettingsService(dao))
    first, second = provider_profiles("ocr")[:2]

    actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=first.id,
            ocr_api_key="first-key",
        )
    )
    response = actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=second.id,
            ocr_api_key="second-key",
        )
    )

    assert response.ocr_provider == second.id
    assert response.ocr_api_key == "second-key"
    assert dao.get(f"{first.id}_api_key") == "first-key"
    assert dao.get(f"{second.id}_api_key") == "second-key"
    assert actions.get_settings(ocr_provider=first.id).ocr_api_key == "first-key"
    assert actions.get_settings(ocr_provider=second.id).ocr_api_key == "second-key"


def test_settings_provider_switch_without_key_does_not_reuse_previous_key(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("ocr_api_key", "")
    actions = SettingsActions(SettingsService(dao))
    first, second = provider_profiles("ocr")[:2]

    actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=first.id,
            ocr_api_key="first-key",
        )
    )
    response = actions.update_settings(SettingsUpdateRequest(ocr_provider=second.id))

    assert response.ocr_provider == second.id
    assert response.ocr_api_key == ""
    assert actions.get_settings(ocr_provider=first.id).ocr_api_key == "first-key"
