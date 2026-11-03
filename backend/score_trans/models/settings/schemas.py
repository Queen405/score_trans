from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from score_trans.models.common.types import (
    AccidentalMode,
    MeasureNumberMode,
    PolyphonyMode,
    TargetKeyOrAuto,
)
from score_trans.models.render.layout import (
    DEFAULT_BEAT_GAP_PERCENT,
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_MEASURES_PER_SYSTEM,
    DEFAULT_FOOTER_PROTECTION_MM,
    DEFAULT_NOTE_SIZE_PERCENT,
    DEFAULT_LYRIC_SIZE_PERCENT,
    DEFAULT_TITLE_SIZE_PERCENT,
    DEFAULT_ANNOTATION_SIZE_PERCENT,
    DEFAULT_PART_GAP_PERCENT,
    DEFAULT_VOICE_GAP_PERCENT,
    DEFAULT_LYRIC_LINE_GAP_PERCENT,
    DEFAULT_LYRIC_NOTE_GAP_PERCENT,
    DEFAULT_HEADER_GAP_MM,
    DEFAULT_MARGIN_BOTTOM_MM,
    DEFAULT_MARGIN_LEFT_MM,
    DEFAULT_MARGIN_RIGHT_MM,
    DEFAULT_MARGIN_TOP_MM,
    MeasuresPerSystem,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    MAX_BEAT_GAP_PERCENT,
    MAX_CONTENT_SCALE_PERCENT,
    MAX_SHORT_NOTE_GAP_PERCENT,
    MAX_SYSTEM_GAP_PERCENT,
    MIN_BEAT_GAP_PERCENT,
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
    audiveris_max_heap: str = "3g"
    audiveris_max_pixel_count: str = "4500000"
    audiveris_auto_upscale: bool = True
    audiveris_min_image_edge: int = 2500
    data_dir: str
    cache_dir: str
    cache_size_bytes: int = 0
    work_dir: str
    target_key: TargetKeyOrAuto = "auto"
    accidental_mode: AccidentalMode = "auto"
    polyphony_mode: PolyphonyMode = "auto"
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
    jianpu_syntax_highlight: bool = True
    jianpu_measure_duration_check: bool = True
    jianpu_auto_transpose: bool = True
    jianpu_content_scale_percent: int = DEFAULT_CONTENT_SCALE_PERCENT
    jianpu_system_gap_percent: int = DEFAULT_SYSTEM_GAP_PERCENT
    jianpu_short_note_gap_percent: int = DEFAULT_SHORT_NOTE_GAP_PERCENT
    jianpu_beat_gap_percent: int = DEFAULT_BEAT_GAP_PERCENT
    jianpu_break_beams_at_beat: bool = False
    jianpu_measures_per_system: MeasuresPerSystem = DEFAULT_MEASURES_PER_SYSTEM
    jianpu_margin_top_mm: float = DEFAULT_MARGIN_TOP_MM
    jianpu_margin_bottom_mm: float = DEFAULT_MARGIN_BOTTOM_MM
    jianpu_margin_left_mm: float = DEFAULT_MARGIN_LEFT_MM
    jianpu_margin_right_mm: float = DEFAULT_MARGIN_RIGHT_MM
    jianpu_header_gap_mm: float = DEFAULT_HEADER_GAP_MM
    jianpu_footer_protection_mm: float = DEFAULT_FOOTER_PROTECTION_MM
    jianpu_note_size_percent: int = DEFAULT_NOTE_SIZE_PERCENT
    jianpu_lyric_size_percent: int = DEFAULT_LYRIC_SIZE_PERCENT
    jianpu_title_size_percent: int = DEFAULT_TITLE_SIZE_PERCENT
    jianpu_annotation_size_percent: int = DEFAULT_ANNOTATION_SIZE_PERCENT
    jianpu_part_gap_percent: int = DEFAULT_PART_GAP_PERCENT
    jianpu_voice_gap_percent: int = DEFAULT_VOICE_GAP_PERCENT
    jianpu_lyric_line_gap_percent: int = DEFAULT_LYRIC_LINE_GAP_PERCENT
    jianpu_lyric_note_gap_percent: int = DEFAULT_LYRIC_NOTE_GAP_PERCENT
    enable_omr_ocr: bool = False
    output_dir: str = ""
    ocr_provider: str
    ocr_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ocr_api_key_set: bool = False
    ocr_api_key: str = ""
    ocr_base_url: str
    ocr_model: str
    ai_provider: str
    ai_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ai_api_key_set: bool = False
    ai_api_key: str = ""
    ai_base_url: str
    ai_model: str
    assistant_provider: str
    assistant_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    assistant_api_key_set: bool = False
    assistant_api_key: str = ""
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
    accidental_mode: AccidentalMode | None = None
    polyphony_mode: PolyphonyMode | None = None
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
    jianpu_beat_gap_percent: int | None = Field(
        default=None,
        ge=MIN_BEAT_GAP_PERCENT,
        le=MAX_BEAT_GAP_PERCENT,
    )
    jianpu_break_beams_at_beat: bool | None = None
    jianpu_measures_per_system: MeasuresPerSystem | None = None
    jianpu_margin_top_mm: float | None = Field(default=None, ge=0, le=50)
    jianpu_margin_bottom_mm: float | None = Field(default=None, ge=0, le=50)
    jianpu_margin_left_mm: float | None = Field(default=None, ge=0, le=50)
    jianpu_margin_right_mm: float | None = Field(default=None, ge=0, le=50)
    jianpu_header_gap_mm: float | None = Field(default=None, ge=0, le=30)
    jianpu_footer_protection_mm: float | None = Field(default=None, ge=0, le=30)
    jianpu_note_size_percent: int | None = Field(default=None, ge=70, le=140)
    jianpu_lyric_size_percent: int | None = Field(default=None, ge=60, le=150)
    jianpu_title_size_percent: int | None = Field(default=None, ge=60, le=160)
    jianpu_annotation_size_percent: int | None = Field(default=None, ge=60, le=150)
    jianpu_part_gap_percent: int | None = Field(default=None, ge=50, le=200)
    jianpu_voice_gap_percent: int | None = Field(default=None, ge=50, le=200)
    jianpu_lyric_line_gap_percent: int | None = Field(default=None, ge=50, le=200)
    jianpu_lyric_note_gap_percent: int | None = Field(default=None, ge=50, le=200)
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
