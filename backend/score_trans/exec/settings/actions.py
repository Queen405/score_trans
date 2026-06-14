from __future__ import annotations

from ...models.common.paths import USER_DATA_ROOT
from ...models.common.types import AccidentalMode
from ...models.settings.config import ToolConfig
from ...models.settings.schemas import (
    CacheCleanupResponse,
    LlmProviderOption,
    SettingsResponse,
    SettingsUpdateRequest,
)
from ...models.settings.provider_profiles import LlmProviderKind, LlmProviderProfile
from ...services.settings.provider_profiles import (
    provider_profiles,
    resolve_provider_profile,
    resolve_provider_profile_or_default,
)
from ...services.settings.api_keys import provider_api_key, provider_api_key_name
from ...services.settings.settings_service import SettingsService
from ...services.storage import CacheService


class SettingsActions:
    def __init__(self, service: SettingsService | None = None) -> None:
        self.service = service or SettingsService()

    def get_config(self) -> ToolConfig:
        return self.service.load()

    def get_settings(
        self,
        *,
        ocr_provider: str | None = None,
        ai_provider: str | None = None,
        assistant_provider: str | None = None,
    ) -> SettingsResponse:
        return self._response(
            ocr_provider=ocr_provider,
            ai_provider=ai_provider,
            assistant_provider=assistant_provider,
        )

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

        if req.accidental_mode is not None:
            self.service.set("accidental_mode", req.accidental_mode)

        if req.work_dir is not None:
            self.service.set("work_dir", req.work_dir)

        if req.ocr_provider is not None:
            self._set_provider("ocr", req.ocr_provider)

        if req.ai_provider is not None:
            self._set_provider("ai", req.ai_provider)

        if req.assistant_provider is not None:
            self._set_provider("assistant", req.assistant_provider)

        if req.ocr_api_key is not None:
            self._set_api_key("ocr", self._current_provider_id("ocr"), req.ocr_api_key)

        if req.ai_api_key is not None:
            self._set_api_key("ai", self._current_provider_id("ai"), req.ai_api_key)

        if req.assistant_api_key is not None:
            self._set_api_key(
                "assistant",
                self._current_provider_id("assistant"),
                req.assistant_api_key,
            )

        if req.omr_preprocess is not None:
            self.service.set("omr_preprocess", "1" if req.omr_preprocess else "0")
            config.omr_preprocess = req.omr_preprocess

        if req.omr_preprocess_long_edge is not None:
            value = max(0, req.omr_preprocess_long_edge)
            self.service.set("omr_preprocess_long_edge", str(value))
            config.omr_preprocess_long_edge = value

        if req.omr_preprocess_binarize is not None:
            self.service.set(
                "omr_preprocess_binarize", "1" if req.omr_preprocess_binarize else "0"
            )
            config.omr_preprocess_binarize = req.omr_preprocess_binarize

        return self._response()

    def clear_cache(self) -> CacheCleanupResponse:
        result = CacheService().clear()
        return CacheCleanupResponse(
            cache_dir=str(result.cache_dir),
            before_bytes=result.before_bytes,
            after_bytes=result.after_bytes,
            freed_bytes=result.freed_bytes,
            removed_items=result.removed_items,
            preserved_uploads=result.preserved_uploads,
        )

    def _current_provider_id(self, kind: LlmProviderKind) -> str:
        return self.service.get_all().get(f"{kind}_provider", "")

    def _migrate_kind_api_key(self, kind: LlmProviderKind, provider_id: str) -> None:
        if not provider_id:
            return
        all_settings = self.service.get_all()
        key = all_settings.get(f"{kind}_api_key", "")
        provider_key_name = provider_api_key_name(provider_id)
        if key and not all_settings.get(provider_key_name, ""):
            self.service.set(provider_key_name, key)

    def _sync_kind_api_key(self, kind: LlmProviderKind, provider_id: str) -> None:
        all_settings = self.service.get_all()
        self.service.set(
            f"{kind}_api_key", all_settings.get(provider_api_key_name(provider_id), "")
        )

    def _set_api_key(self, kind: LlmProviderKind, provider_id: str, key: str) -> None:
        if provider_id:
            self.service.set(provider_api_key_name(provider_id), key)
        self.service.set(f"{kind}_api_key", key)

    def _set_provider(
        self, kind: LlmProviderKind, provider_id: str
    ) -> LlmProviderProfile:
        self._migrate_kind_api_key(kind, self._current_provider_id(kind))
        profile = resolve_provider_profile(kind, provider_id)
        prefix = kind
        self.service.set(f"{prefix}_provider", profile.id)
        self.service.set(f"{prefix}_base_url", profile.base_url)
        self.service.set(f"{prefix}_model", profile.model)
        if kind == "ocr":
            self.service.set("ocr_fallback_model", profile.fallback_model)
        self._sync_kind_api_key(kind, profile.id)
        return profile

    def _response(
        self,
        *,
        ocr_provider: str | None = None,
        ai_provider: str | None = None,
        assistant_provider: str | None = None,
    ) -> SettingsResponse:
        all_settings = self.service.get_all()
        saved_ocr_profile = resolve_provider_profile_or_default(
            "ocr", all_settings.get("ocr_provider")
        )
        saved_ai_profile = resolve_provider_profile_or_default(
            "ai", all_settings.get("ai_provider")
        )
        saved_assistant_profile = resolve_provider_profile_or_default(
            "assistant",
            all_settings.get("assistant_provider"),
        )
        key_settings = {
            **all_settings,
            "ocr_provider": saved_ocr_profile.id,
            "ai_provider": saved_ai_profile.id,
            "assistant_provider": saved_assistant_profile.id,
        }
        ocr_profile = resolve_provider_profile_or_default(
            "ocr", ocr_provider or saved_ocr_profile.id
        )
        ai_profile = resolve_provider_profile_or_default(
            "ai", ai_provider or saved_ai_profile.id
        )
        assistant_profile = resolve_provider_profile_or_default(
            "assistant",
            assistant_provider or saved_assistant_profile.id,
        )
        ocr_api_key = provider_api_key(key_settings, "ocr", ocr_profile.id)
        ai_api_key = provider_api_key(key_settings, "ai", ai_profile.id)
        assistant_api_key = provider_api_key(
            key_settings, "assistant", assistant_profile.id
        )
        config = self.service.load()
        cache_size_bytes = CacheService(cache_dir=config.work_dir).size_bytes()
        return SettingsResponse(
            audiveris_path=all_settings.get("audiveris_path", ""),
            java_home=all_settings.get("java_home", ""),
            data_dir=str(USER_DATA_ROOT),
            cache_dir=str(config.work_dir),
            cache_size_bytes=cache_size_bytes,
            work_dir=str(config.work_dir),
            output_dir=all_settings.get("output_dir", ""),
            target_key=all_settings.get("target_key", "C"),
            accidental_mode=_accidental_mode(all_settings.get("accidental_mode")),
            ocr_provider=ocr_profile.id,
            ocr_provider_options=_provider_options("ocr"),
            ocr_api_key=ocr_api_key,
            ocr_api_key_set=bool(ocr_api_key),
            ocr_base_url=ocr_profile.base_url,
            ocr_model=ocr_profile.model,
            ai_provider=ai_profile.id,
            ai_provider_options=_provider_options("ai"),
            ai_api_key=ai_api_key,
            ai_api_key_set=bool(ai_api_key),
            ai_base_url=ai_profile.base_url,
            ai_model=ai_profile.model,
            assistant_provider=assistant_profile.id,
            assistant_provider_options=_provider_options("assistant"),
            assistant_api_key=assistant_api_key,
            assistant_api_key_set=bool(assistant_api_key),
            assistant_base_url=assistant_profile.base_url,
            assistant_model=assistant_profile.model,
            omr_preprocess=self.service.get_bool("omr_preprocess", True),
            omr_preprocess_long_edge=self.service.get_int(
                "omr_preprocess_long_edge", 3600
            ),
            omr_preprocess_binarize=self.service.get_bool(
                "omr_preprocess_binarize", False
            ),
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


def _accidental_mode(value: str | None) -> AccidentalMode:
    if value in {"auto", "sharp", "flat"}:
        return value
    return "auto"
