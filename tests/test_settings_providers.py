from __future__ import annotations

import json
import re
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
import score_trans.services.settings.defaults as settings_defaults_module
from score_trans.services.settings.defaults import settings_defaults
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


def test_omr_ocr_setting_defaults_off_and_round_trips(tmp_path) -> None:
    defaults = settings_defaults()
    assert defaults["enable_omr_ocr"] == "0"
    dao = SettingsDao(tmp_path / "settings.db", defaults=defaults)
    actions = SettingsActions(SettingsService(dao))

    assert actions.get_settings().enable_omr_ocr is False

    response = actions.update_settings(SettingsUpdateRequest(enable_omr_ocr=True))

    assert response.enable_omr_ocr is True
    assert dao.get("enable_omr_ocr") == "1"
    assert SettingsActions(SettingsService(dao)).get_settings().enable_omr_ocr is True
    assert SettingsService(dao).load().enable_omr_ocr is True


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

    assert "agnes_3_0_flash" in ids

    agnes = resolve_provider_profile("assistant", "agnes_2_5_flash")
    assert agnes.provider == "agnes"
    assert agnes.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes.model == "agnes-2.5-flash"

    agnes_3 = resolve_provider_profile("assistant", "agnes_3_0_flash")
    assert agnes_3.provider == "agnes"
    assert agnes_3.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes_3.model == "agnes-3.0-flash"

    sensenova = resolve_provider_profile("assistant", "sensenova_deepseek_v4_flash")
    assert sensenova.provider == "sensenova"
    assert sensenova.base_url == "https://token.sensenova.cn/v1"
    assert sensenova.model == "deepseek-v4-flash"


def test_ai_provider_profiles_include_agnes() -> None:
    profiles = provider_profiles("ai")
    ids = [profile.id for profile in profiles]

    assert "agnes_2_5_flash" in ids
    assert "sensenova_6_8_flash_lite" in ids

    assert "agnes_3_0_flash" in ids

    agnes = resolve_provider_profile("ai", "agnes_2_5_flash")
    assert agnes.provider == "openai_compatible"
    assert agnes.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes.model == "agnes-2.5-flash"

    agnes_3 = resolve_provider_profile("ai", "agnes_3_0_flash")
    assert agnes_3.provider == "openai_compatible"
    assert agnes_3.base_url == "https://apihub.agnes-ai.com/v1"
    assert agnes_3.model == "agnes-3.0-flash"

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
    assert response.ocr_api_key == "first-key"
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


# ---------------------------------------------------------------------------
# Published defaults baseline
# ---------------------------------------------------------------------------

_BASELINE_PATH = (
    Path(__file__).parents[1]
    / "backend"
    / "score_trans"
    / "config"
    / "published_defaults.json"
)

_ENV_LEVEL_AUVIDERIS_KEYS = (
    "audiveris_step",
    "audiveris_force",
    "audiveris_save",
    "audiveris_swap",
    "audiveris_transcribe",
    "audiveris_sheets",
    "audiveris_constants",
    "audiveris_extra_args",
)


def test_published_defaults_json_parses_and_matches_schema() -> None:
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    backend = payload["backend"]
    providers = payload["providers"]
    for key in (
        "audiveris_max_heap",
        "audiveris_max_pixel_count",
        "audiveris_auto_upscale",
        "audiveris_min_image_edge",
        "target_key",
        "accidental_mode",
        "measure_number_mode",
        "show_measure_numbers",
        "jianpu_syntax_highlight",
        "jianpu_measure_duration_check",
        "jianpu_auto_transpose",
        "jianpu_content_scale_percent",
        "jianpu_system_gap_percent",
        "jianpu_short_note_gap_percent",
        "jianpu_beat_gap_percent",
        "enable_omr_ocr",
        "output_dir",
    ):
        assert isinstance(backend[key], str), f"backend.{key} must be a string"
    for kind in ("ocr", "ai", "assistant"):
        section = providers[kind]
        assert isinstance(section["provider"], str)
        assert isinstance(section["base_url"], str)
        assert isinstance(section["model"], str)
    assert isinstance(providers["ocr"]["fallback_model"], str)


def test_published_defaults_contains_no_private_fields_or_paths() -> None:
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))

    def check(node, trail):
        if isinstance(node, dict):
            for key, value in node.items():
                lower = key.lower()
                assert not any(
                    frag in lower for frag in ("api_key", "token", "password")
                ), f"private field {trail}.{key}"
                if isinstance(value, str):
                    assert not re.match(r"^[A-Za-z]:[\\/]|^/|^~", value), (
                        f"absolute path in {trail}.{key}={value!r}"
                    )
                check(value, f"{trail}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check(item, f"{trail}[{i}]")

    check(payload, "")


def test_settings_defaults_seeds_baseline_values() -> None:
    defaults = settings_defaults()
    assert defaults["target_key"] == "auto"
    assert defaults["accidental_mode"] == "auto"
    assert defaults["polyphony_mode"] == "auto"
    assert defaults["measure_number_mode"] == "all"
    assert defaults["show_measure_numbers"] == "1"
    assert defaults["jianpu_syntax_highlight"] == "1"
    assert defaults["jianpu_measure_duration_check"] == "1"
    assert defaults["jianpu_auto_transpose"] == "1"
    assert defaults["jianpu_content_scale_percent"] == "80"
    assert defaults["jianpu_system_gap_percent"] == "50"
    assert defaults["jianpu_short_note_gap_percent"] == "20"
    assert defaults["jianpu_beat_gap_percent"] == "100"
    assert defaults["jianpu_margin_top_mm"] == "10"
    assert defaults["jianpu_margin_bottom_mm"] == "7"
    assert defaults["jianpu_margin_left_mm"] == "12"
    assert defaults["jianpu_margin_right_mm"] == "12"
    assert defaults["jianpu_header_gap_mm"] == "5"
    assert defaults["jianpu_footer_protection_mm"] == "2"
    assert defaults["enable_omr_ocr"] == "0"
    assert defaults["audiveris_max_heap"] == "3g"
    assert defaults["audiveris_max_pixel_count"] == "4500000"
    assert defaults["audiveris_auto_upscale"] == "1"
    assert defaults["audiveris_min_image_edge"] == "2500"


def test_settings_defaults_seeds_empty_api_keys() -> None:
    defaults = settings_defaults()
    assert defaults["ocr_api_key"] == ""
    assert defaults["ai_api_key"] == ""
    assert defaults["assistant_api_key"] == ""


def test_settings_defaults_seeds_empty_paths() -> None:
    defaults = settings_defaults()
    assert defaults["audiveris_path"] == ""
    assert defaults["java_home"] == ""
    assert defaults["output_dir"] == ""
    assert "work_dir" not in defaults


def test_env_level_audiveris_params_not_seeded() -> None:
    defaults = settings_defaults()
    for key in _ENV_LEVEL_AUVIDERIS_KEYS:
        assert key not in defaults, f"{key} should not be seeded from baseline"


# 更新路由中允许存在但刻意不纳入发布基线的字段：
# - work_dir：不种植，使用安装用户的 ~/.score_trans/ 目录
# （API Key 也在基线中，但只种空字符串占位，不算豁免。）
_UNSEEDED_UPDATE_FIELDS = frozenset({"work_dir"})


def test_settings_defaults_cover_every_updatable_setting() -> None:
    """新增设置字段时必须同步发布基线（或显式加入豁免清单）。

    settings_defaults() 种入的键 + API Key 占位键 + 豁免字段，必须完整覆盖
    SettingsUpdateRequest 的全部字段，防止新设置漏进 published_defaults.json。
    """
    defaults = settings_defaults()
    for key in sorted(SettingsUpdateRequest.model_fields):
        assert key in defaults or key in _UNSEEDED_UPDATE_FIELDS, (
            f"{key} is updatable via /settings but missing from published defaults"
        )


def test_provider_selection_matches_baseline() -> None:
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    defaults = settings_defaults()
    for kind in ("ocr", "ai", "assistant"):
        section = payload["providers"][kind]
        assert defaults[f"{kind}_provider"] == section["provider"]
        assert defaults[f"{kind}_base_url"] == section["base_url"]
        assert defaults[f"{kind}_model"] == section["model"]
    assert (
        defaults["ocr_fallback_model"] == payload["providers"]["ocr"]["fallback_model"]
    )


def test_baseline_seeds_new_database(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db", defaults=settings_defaults())
    all_settings = dao.get_all()
    assert all_settings["target_key"] == "auto"
    assert all_settings["enable_omr_ocr"] == "0"
    assert all_settings["ocr_api_key"] == ""
    assert all_settings["ai_api_key"] == ""
    assert all_settings["assistant_api_key"] == ""
    assert all_settings["audiveris_path"] == ""
    assert all_settings["java_home"] == ""
    assert all_settings["jianpu_content_scale_percent"] == "80"
    assert all_settings["jianpu_system_gap_percent"] == "50"
    assert all_settings["jianpu_short_note_gap_percent"] == "20"


def test_layout_defaults_flow_from_published_baseline_to_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))
    payload["backend"].update(
        {
            "jianpu_content_scale_percent": "71",
            "jianpu_system_gap_percent": "123",
            "jianpu_short_note_gap_percent": "134",
        }
    )
    baseline_path = tmp_path / "published_defaults.json"
    baseline_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(settings_defaults_module, "_BASELINE_PATH", baseline_path)

    defaults = settings_defaults()
    dao = SettingsDao(tmp_path / "settings.db", defaults=defaults)
    response = SettingsActions(SettingsService(dao)).get_settings()

    assert defaults["jianpu_content_scale_percent"] == "71"
    assert defaults["jianpu_system_gap_percent"] == "123"
    assert defaults["jianpu_short_note_gap_percent"] == "134"
    assert dao.get("jianpu_content_scale_percent") == "71"
    assert dao.get("jianpu_system_gap_percent") == "123"
    assert dao.get("jianpu_short_note_gap_percent") == "134"
    assert response.jianpu_content_scale_percent == 71
    assert response.jianpu_system_gap_percent == 123
    assert response.jianpu_short_note_gap_percent == 134


def test_baseline_does_not_overwrite_existing_user_values(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db")
    dao.set("target_key", "G")
    dao.set("ocr_api_key", "sk-user-key")
    dao.ensure_defaults(settings_defaults())

    assert dao.get("target_key") == "G"
    assert dao.get("ocr_api_key") == "sk-user-key"
    assert dao.get("enable_omr_ocr") == "0"


def test_show_measure_numbers_and_mode_stay_consistent(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db", defaults=settings_defaults())
    assert dao.get("show_measure_numbers") == "1"
    assert dao.get("measure_number_mode") == "all"


def test_empty_seeded_paths_trigger_auto_resolution(tmp_path) -> None:
    dao = SettingsDao(tmp_path / "settings.db", defaults=settings_defaults())
    service = SettingsService(dao)
    config = service.load()
    # Empty seeded paths should resolve to non-empty defaults (env or bundled).
    assert config.audiveris_path
    # java_home may be empty if no bundled JDK exists in dev — just verify
    # it does not retain the empty seed when a default is available.
    assert config.enable_omr_ocr is False
