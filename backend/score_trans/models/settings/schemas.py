from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from score_trans.models.common.types import (
    AccidentalMode,
    MeasureNumberMode,
    MidiTempo,
    TargetKeyOrAuto,
)
from score_trans.models.render.layout import (
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    MAX_CONTENT_SCALE_PERCENT,
    MAX_SHORT_NOTE_GAP_PERCENT,
    MAX_SYSTEM_GAP_PERCENT,
    MIN_CONTENT_SCALE_PERCENT,
    MIN_SHORT_NOTE_GAP_PERCENT,
    MIN_SYSTEM_GAP_PERCENT,
)


class LlmProviderOption(BaseModel):
    id: str
    label: str
    provider: str
    base_url: str
    model: str
    description: str = ""


class SettingsResponse(BaseModel):
    audiveris_path: str
    java_home: str
    audiveris_max_heap: str = "2g"
    audiveris_max_pixel_count: str = "20000000"
    audiveris_auto_upscale: bool = True
    audiveris_min_image_edge: int = 2500
    data_dir: str
    cache_dir: str
    cache_size_bytes: int = 0
    work_dir: str
    target_key: TargetKeyOrAuto = "auto"
    midi_tempo: MidiTempo = "auto"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
    jianpu_syntax_highlight: bool = False
    jianpu_measure_duration_check: bool = False
    jianpu_auto_transpose: bool = False
    jianpu_content_scale_percent: int = DEFAULT_CONTENT_SCALE_PERCENT
    jianpu_system_gap_percent: int = DEFAULT_SYSTEM_GAP_PERCENT
    jianpu_short_note_gap_percent: int = DEFAULT_SHORT_NOTE_GAP_PERCENT
    enable_omr_ocr: bool = True
    output_dir: str = ""
    ocr_provider: str
    ocr_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ocr_api_key_set: bool = False
    ocr_base_url: str
    ocr_model: str
    ai_provider: str
    ai_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ai_api_key_set: bool = False
    ai_base_url: str
    ai_model: str
    assistant_provider: str
    assistant_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    assistant_api_key_set: bool = False
    assistant_base_url: str
    assistant_model: str


class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    java_home: str | None = None
    audiveris_max_heap: Literal["1g", "2g", "3g", "4g"] | None = None
    audiveris_max_pixel_count: str | None = None
    audiveris_auto_upscale: bool | None = None
    audiveris_min_image_edge: int | None = Field(default=None, ge=0, le=10000)
    output_dir: str | None = None
    target_key: TargetKeyOrAuto | None = None
    midi_tempo: MidiTempo | None = None
    accidental_mode: AccidentalMode | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode | None = None
    jianpu_syntax_highlight: bool | None = None
    jianpu_measure_duration_check: bool | None = None
    jianpu_auto_transpose: bool | None = None
    jianpu_content_scale_percent: int | None = Field(
        default=None,
        ge=MIN_CONTENT_SCALE_PERCENT,
        le=MAX_CONTENT_SCALE_PERCENT,
    )
    jianpu_system_gap_percent: int | None = Field(
        default=None,
        ge=MIN_SYSTEM_GAP_PERCENT,
        le=MAX_SYSTEM_GAP_PERCENT,
    )
    jianpu_short_note_gap_percent: int | None = Field(
        default=None,
        ge=MIN_SHORT_NOTE_GAP_PERCENT,
        le=MAX_SHORT_NOTE_GAP_PERCENT,
    )
    enable_omr_ocr: bool | None = None
    work_dir: str | None = None
    ocr_provider: str | None = None
    ocr_api_key: str | None = None
    ocr_base_url: str | None = Field(default=None, max_length=2048)
    ocr_model: str | None = Field(default=None, max_length=256)
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_base_url: str | None = Field(default=None, max_length=2048)
    ai_model: str | None = Field(default=None, max_length=256)
    assistant_provider: str | None = None
    assistant_api_key: str | None = None
    assistant_base_url: str | None = Field(default=None, max_length=2048)
    assistant_model: str | None = Field(default=None, max_length=256)

    @field_validator(
        "ocr_base_url",
        "ai_base_url",
        "assistant_base_url",
        mode="before",
    )
    @classmethod
    def validate_provider_base_url(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            raise ValueError("provider base URL must not be empty")
        try:
            parsed = urlsplit(cleaned)
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("provider base URL is invalid") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("provider base URL must use HTTP or HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("provider base URL must not contain credentials")
        return cleaned

    @field_validator("ocr_model", "ai_model", "assistant_model", mode="before")
    @classmethod
    def validate_provider_model(cls, value: object) -> object:
        if value is None or not isinstance(value, str):
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("provider model must not be empty")
        return cleaned


class CacheCleanupResponse(BaseModel):
    cache_dir: str
    before_bytes: int
    after_bytes: int
    freed_bytes: int
    removed_items: int
    preserved_uploads: int
