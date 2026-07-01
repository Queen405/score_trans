from __future__ import annotations

import pytest

from score_trans.api.app import create_app
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.settings.actions import SettingsActions
from score_trans.models.settings.schemas import SettingsUpdateRequest
from score_trans.services.settings.api_keys import provider_api_key_name
from score_trans.services.settings.provider_profiles import (
    provider_profiles,
    resolve_provider_profile,
)
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
    ocr_profile = provider_profiles("ocr")[0]
    ai_profile = provider_profiles("ai")[0]
    assistant_profile = provider_profiles("assistant")[0]

    response = actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=ocr_profile.id,
            ai_provider=ai_profile.id,
            assistant_provider=assistant_profile.id,
        )
    )
    resolved_ocr = resolve_provider_profile("ocr", ocr_profile.id)
    resolved_ai = resolve_provider_profile("ai", ai_profile.id)
    resolved_assistant = resolve_provider_profile("assistant", assistant_profile.id)

    assert response.ocr_provider == resolved_ocr.id
    assert response.ocr_base_url == resolved_ocr.base_url
    assert response.ocr_model == resolved_ocr.model
    assert response.ai_provider == resolved_ai.id
    assert response.ai_base_url == resolved_ai.base_url
    assert response.ai_model == resolved_ai.model
    assert response.assistant_provider == resolved_assistant.id
    assert response.assistant_model == resolved_assistant.model
    assert dao.get("ocr_base_url") == resolved_ocr.base_url
    assert dao.get("ai_model") == resolved_ai.model
    assert dao.get("assistant_model") == resolved_assistant.model


def test_settings_rejects_unknown_provider(tmp_path) -> None:
    actions = SettingsActions(SettingsService(SettingsDao(tmp_path / "settings.db")))

    with pytest.raises(ValueError, match="未知OCR provider"):
        actions.update_settings(SettingsUpdateRequest(ocr_provider="custom_model"))


def test_settings_saves_api_keys_per_provider(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("ocr_api_key", "")
    actions = SettingsActions(SettingsService(dao))
    first = provider_profiles("ocr")[0]

    response = actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=first.id,
            ocr_api_key="first-key",
        )
    )

    assert response.ocr_provider == first.id
    assert response.ocr_api_key_set is True
    assert "ocr_api_key" not in response.model_dump()
    assert dao.get(provider_api_key_name(first.id)) == "first-key"
    assert actions.get_settings(ocr_provider=first.id).ocr_api_key_set is True


def test_settings_provider_switch_without_key_does_not_reuse_previous_key(
    tmp_path,
) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("ocr_api_key", "")
    actions = SettingsActions(SettingsService(dao))
    profiles = provider_profiles("ocr")
    if len(profiles) < 2:
        pytest.skip("requires at least two configured OCR providers")
    first, second = profiles[:2]

    actions.update_settings(
        SettingsUpdateRequest(
            ocr_provider=first.id,
            ocr_api_key="first-key",
        )
    )
    response = actions.update_settings(SettingsUpdateRequest(ocr_provider=second.id))

    assert response.ocr_provider == second.id
    assert response.ocr_api_key_set is False
    assert dao.get(provider_api_key_name(first.id)) == "first-key"
    assert actions.get_settings(ocr_provider=first.id).ocr_api_key_set is True
