from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from score_trans.api.app import create_app
from score_trans.dao.ai.chat_dao import AiChatDao
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.settings.actions import SettingsActions
from score_trans.models.settings.schemas import SettingsUpdateRequest
from score_trans.services.ai.chat_service import AiChatService
from score_trans.services.ai.transcription import AiTranscriptionService
from score_trans.services.ocr.providers import create_configured_ocr_provider
from score_trans.services.settings.api_keys import provider_api_key_name
from score_trans.services.settings.provider_profiles import (
    provider_profiles,
    resolve_provider_profile,
)
from score_trans.services.settings.settings_service import SettingsService


def test_env_example_documents_optional_path_and_ai_prompt_overrides() -> None:
    example = (
        Path(__file__).parents[1] / "backend" / "score_trans" / "config" / "env.example"
    ).read_text(encoding="utf-8")

    for variable in (
        "SCORE_TRANS_WORKDIR=",
        "SCORE_TRANS_JAVA_HOME=",
        "SCORE_TRANS_OUTPUT_DIR=",
        "SCORE_TRANS_AI_SYSTEM_MSG=",
    ):
        assert variable in example


def test_settings_update_schema_accepts_provider_endpoint_overrides() -> None:
    schema = create_app().openapi()["components"]["schemas"]["SettingsUpdateRequest"]
    properties = schema["properties"]

    assert "ocr_provider" in properties
    assert "ai_provider" in properties
    assert "assistant_provider" in properties
    assert "ocr_base_url" in properties
    assert "ocr_model" in properties
    assert "ai_base_url" in properties
    assert "ai_model" in properties
    assert "assistant_base_url" in properties
    assert "assistant_model" in properties


def test_settings_provider_endpoint_overrides_are_saved_and_returned(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    actions = SettingsActions(SettingsService(dao))

    response = actions.update_settings(
        SettingsUpdateRequest(
            ocr_base_url="https://ocr.example.com/v1/",
            ocr_model="ocr-custom",
            ai_base_url="https://ai.example.com/v1",
            ai_model="ai-custom",
            assistant_base_url="https://assistant.example.com/v1",
            assistant_model="assistant-custom",
        )
    )

    assert response.ocr_base_url == "https://ocr.example.com/v1"
    assert response.ocr_model == "ocr-custom"
    assert response.ai_base_url == "https://ai.example.com/v1"
    assert response.ai_model == "ai-custom"
    assert response.assistant_base_url == "https://assistant.example.com/v1"
    assert response.assistant_model == "assistant-custom"
    assert dao.get("ocr_base_url") == "https://ocr.example.com/v1"
    assert dao.get("assistant_model") == "assistant-custom"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ocr_base_url", "ftp://example.com/v1"),
        ("ai_base_url", "https://user:secret@example.com/v1"),
        ("assistant_base_url", "not-a-url"),
        ("ocr_model", " "),
        ("ai_model", "x" * 257),
        ("audiveris_max_heap", "8g"),
    ],
)
def test_settings_update_rejects_invalid_endpoint_or_heap(field, value) -> None:
    with pytest.raises(ValidationError):
        SettingsUpdateRequest(**{field: value})


def test_settings_preserves_string_zero_pixel_count(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("audiveris_max_pixel_count", "0")

    assert SettingsService(dao).load().audiveris_max_pixel_count == "0"


def test_configured_services_use_saved_endpoint_and_model_overrides(
    tmp_path,
    monkeypatch,
) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    ocr_profile = next(
        profile for profile in provider_profiles("ocr") if profile.provider != "mock"
    )
    ai_profile = provider_profiles("ai")[0]
    assistant_profile = provider_profiles("assistant")[0]
    for kind, profile in (
        ("ocr", ocr_profile),
        ("ai", ai_profile),
        ("assistant", assistant_profile),
    ):
        dao.set(f"{kind}_provider", profile.id)
        dao.set(f"{kind}_base_url", f"https://{kind}.example.com/v1")
        dao.set(f"{kind}_model", f"{kind}-custom")

    monkeypatch.setattr(
        "score_trans.services.ocr.providers.configured_settings_dao",
        lambda: dao,
    )
    monkeypatch.setattr(
        "score_trans.services.ai.transcription.service.configured_settings_dao",
        lambda: dao,
    )

    ocr_provider = create_configured_ocr_provider()
    ai_provider = AiTranscriptionService().provider
    chat = AiChatService(
        dao=AiChatDao(tmp_path / "ai-chat.db"),
        settings=dao,
    )

    assert ocr_provider.base_url == "https://ocr.example.com/v1"
    assert ocr_provider.model == "ocr-custom"
    assert ai_provider.base_url == "https://ai.example.com/v1"
    assert ai_provider.model == "ai-custom"
    assert chat.provider.base_url == "https://assistant.example.com/v1"
    assert chat.provider.model == "assistant-custom"


def test_settings_dao_injected_defaults_fill_missing_without_overwriting(
    tmp_path,
) -> None:
    dao = SettingsDao(
        tmp_path / "settings.db",
        defaults={"ocr_model": "environment-model"},
    )
    dao.set("ocr_model", "user-model")

    dao.ensure_defaults(
        {
            "ocr_model": "new-environment-model",
            "ai_model": "new-ai-model",
        }
    )

    assert dao.get("ocr_model") == "user-model"
    assert dao.get("ai_model") == "new-ai-model"


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


def test_assistant_provider_profiles_include_agnes_and_sensenova() -> None:
    profiles = provider_profiles("assistant")
    ids = [profile.id for profile in profiles]

    assert "agnes_2_5_flash" in ids
    assert "sensenova_deepseek_v4_flash" in ids

    agnes = resolve_provider_profile("assistant", "agnes_2_5_flash")
    assert agnes.provider == "agnes"
    assert agnes.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes.model == "agnes-2.5-flash"

    sensenova = resolve_provider_profile("assistant", "sensenova_deepseek_v4_flash")
    assert sensenova.provider == "sensenova"
    assert sensenova.base_url == "https://token.sensenova.cn/v1"
    assert sensenova.model == "deepseek-v4-flash"


def test_ai_provider_profiles_include_agnes() -> None:
    profiles = provider_profiles("ai")
    ids = [profile.id for profile in profiles]

    assert "agnes_2_5_flash" in ids
    assert "sensenova_6_8_flash_lite" in ids

    agnes = resolve_provider_profile("ai", "agnes_2_5_flash")
    assert agnes.provider == "openai_compatible"
    assert agnes.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes.model == "agnes-2.5-flash"

    sensenova = resolve_provider_profile("ai", "sensenova_6_8_flash_lite")
    assert sensenova.provider == "sensenova"
    assert sensenova.base_url == "https://token.sensenova.cn/v1"
    assert sensenova.model == "sensenova-6.8-flash-lite"


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
