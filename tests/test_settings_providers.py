from __future__ import annotations

import pytest

from score_trans.api.app import create_app
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.settings.actions import SettingsActions
from score_trans.models.settings.provider_profiles import DASHSCOPE_BASE_URL, XIAOMI_MIMO_BASE_URL
from score_trans.models.settings.schemas import SettingsUpdateRequest
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

    assert response.ocr_provider == "dashscope_qwen_vl_ocr"
    assert response.ocr_base_url == DASHSCOPE_BASE_URL
    assert response.ocr_model == "qwen-vl-ocr"
    assert response.ai_provider == "xiaomi_mimo_v25"
    assert response.ai_base_url == XIAOMI_MIMO_BASE_URL
    assert response.ai_model == "mimo-v2.5"
    assert response.assistant_provider == "dashscope_qwen_plus"
    assert response.assistant_model == "qwen-plus"
    assert dao.get("ocr_base_url") == DASHSCOPE_BASE_URL
    assert dao.get("ai_model") == "mimo-v2.5"
    assert dao.get("assistant_model") == "qwen-plus"


def test_settings_rejects_unknown_provider(tmp_path) -> None:
    actions = SettingsActions(SettingsService(SettingsDao(tmp_path / "settings.db")))

    with pytest.raises(ValueError, match="未知OCR provider"):
        actions.update_settings(SettingsUpdateRequest(ocr_provider="custom_model"))
