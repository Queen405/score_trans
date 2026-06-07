from __future__ import annotations

from ...models.settings.provider_profiles import (
    LlmProviderKind,
    LlmProviderProfile,
    provider_profiles,
    resolve_provider_profile,
    resolve_provider_profile_or_default,
)
from ...models.settings.config import ToolConfig
from ...models.settings.schemas import LlmProviderOption, SettingsResponse, SettingsUpdateRequest
from ...services.settings.settings_service import SettingsService


class SettingsActions:
    def __init__(self, service: SettingsService | None = None) -> None:
        self.service = service or SettingsService()

    def get_config(self) -> ToolConfig:
        return self.service.load()

    def get_settings(self) -> SettingsResponse:
        return self._response()

    def update_settings(self, req: SettingsUpdateRequest) -> SettingsResponse:
        config = self.service.load()
        if req.audiveris_path is not None:
            self.service.set("audiveris_path", req.audiveris_path)
            config.audiveris_path = req.audiveris_path

        if req.java_home is not None:
            self.service.set("java_home", req.java_home)
            config.java_home = req.java_home

        if req.output_dir is not None:
            self.service.set("output_dir", req.output_dir)

        if req.target_key is not None:
            self.service.set("target_key", req.target_key)

        if req.work_dir is not None:
            self.service.set("work_dir", req.work_dir)

        if req.ocr_api_key is not None:
            self.service.set("ocr_api_key", req.ocr_api_key)

        if req.ocr_provider is not None:
            self._set_provider("ocr", req.ocr_provider)

        if req.ai_api_key is not None:
            self.service.set("ai_api_key", req.ai_api_key)

        if req.ai_provider is not None:
            self._set_provider("ai", req.ai_provider)

        if req.assistant_api_key is not None:
            self.service.set("assistant_api_key", req.assistant_api_key)

        if req.assistant_provider is not None:
            self._set_provider("assistant", req.assistant_provider)

        if req.omr_preprocess is not None:
            self.service.set("omr_preprocess", "1" if req.omr_preprocess else "0")
            config.omr_preprocess = req.omr_preprocess

        if req.omr_preprocess_long_edge is not None:
            value = max(0, req.omr_preprocess_long_edge)
            self.service.set("omr_preprocess_long_edge", str(value))
            config.omr_preprocess_long_edge = value

        if req.omr_preprocess_binarize is not None:
            self.service.set("omr_preprocess_binarize", "1" if req.omr_preprocess_binarize else "0")
            config.omr_preprocess_binarize = req.omr_preprocess_binarize

        return self._response()

    def _set_provider(self, kind: LlmProviderKind, provider_id: str) -> LlmProviderProfile:
        profile = resolve_provider_profile(kind, provider_id)
        prefix = kind
        self.service.set(f"{prefix}_provider", profile.id)
        self.service.set(f"{prefix}_base_url", profile.base_url)
        self.service.set(f"{prefix}_model", profile.model)
        if kind == "ocr":
            self.service.set("ocr_fallback_model", profile.fallback_model)
        return profile

    def _response(self) -> SettingsResponse:
        all_settings = self.service.get_all()
        ocr_profile = resolve_provider_profile_or_default("ocr", all_settings.get("ocr_provider"))
        ai_profile = resolve_provider_profile_or_default("ai", all_settings.get("ai_provider"))
        assistant_profile = resolve_provider_profile_or_default(
            "assistant",
            all_settings.get("assistant_provider"),
        )
        return SettingsResponse(
            audiveris_path=all_settings.get("audiveris_path", ""),
            java_home=all_settings.get("java_home", ""),
            work_dir=str(self.service.load().work_dir),
            output_dir=all_settings.get("output_dir", ""),
            target_key=all_settings.get("target_key", "C"),
            ocr_provider=ocr_profile.id,
            ocr_provider_options=_provider_options("ocr"),
            ocr_api_key=all_settings.get("ocr_api_key", ""),
            ocr_api_key_set=bool(all_settings.get("ocr_api_key", "")),
            ocr_base_url=ocr_profile.base_url,
            ocr_model=ocr_profile.model,
            ai_provider=ai_profile.id,
            ai_provider_options=_provider_options("ai"),
            ai_api_key=all_settings.get("ai_api_key", ""),
            ai_api_key_set=bool(all_settings.get("ai_api_key", "")),
            ai_base_url=ai_profile.base_url,
            ai_model=ai_profile.model,
            assistant_provider=assistant_profile.id,
            assistant_provider_options=_provider_options("assistant"),
            assistant_api_key=all_settings.get("assistant_api_key", ""),
            assistant_api_key_set=bool(all_settings.get("assistant_api_key", "")),
            assistant_base_url=assistant_profile.base_url,
            assistant_model=assistant_profile.model,
            omr_preprocess=self.service.get_bool("omr_preprocess", True),
            omr_preprocess_long_edge=self.service.get_int("omr_preprocess_long_edge", 3600),
            omr_preprocess_binarize=self.service.get_bool("omr_preprocess_binarize", False),
        )


def _provider_options(kind: LlmProviderKind) -> list[LlmProviderOption]:
    return [
        LlmProviderOption(
            id=profile.id,
            label=profile.label,
            provider=profile.provider,
            base_url=profile.base_url,
            model=profile.model,
            description=profile.description,
        )
        for profile in provider_profiles(kind)
    ]
