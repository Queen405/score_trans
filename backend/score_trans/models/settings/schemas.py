from __future__ import annotations

from pydantic import BaseModel, Field

from score_trans.config.settings import (
    AI_BASE_URL,
    AI_MODEL,
    AI_PROVIDER,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
    ASSISTANT_PROVIDER,
    OCR_BASE_URL,
    OCR_MODEL,
    OCR_PROVIDER,
    OMR_PREPROCESS,
    OMR_PREPROCESS_BINARIZE,
    OMR_PREPROCESS_LONG_EDGE,
)
from score_trans.models.common.types import AccidentalMode, MeasureNumberMode, TargetKey


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
    data_dir: str
    cache_dir: str
    cache_size_bytes: int = 0
    work_dir: str
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
    jianpu_syntax_highlight: bool = False
    output_dir: str = ""
    ocr_provider: str = OCR_PROVIDER
    ocr_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ocr_api_key: str = ""
    ocr_api_key_set: bool = False
    ocr_base_url: str = OCR_BASE_URL
    ocr_model: str = OCR_MODEL
    ai_provider: str = AI_PROVIDER
    ai_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    ai_api_key: str = ""
    ai_api_key_set: bool = False
    ai_base_url: str = AI_BASE_URL
    ai_model: str = AI_MODEL
    assistant_provider: str = ASSISTANT_PROVIDER
    assistant_provider_options: list[LlmProviderOption] = Field(default_factory=list)
    assistant_api_key: str = ""
    assistant_api_key_set: bool = False
    assistant_base_url: str = ASSISTANT_BASE_URL
    assistant_model: str = ASSISTANT_MODEL
    omr_preprocess: bool = OMR_PREPROCESS
    omr_preprocess_long_edge: int = OMR_PREPROCESS_LONG_EDGE
    omr_preprocess_binarize: bool = OMR_PREPROCESS_BINARIZE


class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    java_home: str | None = None
    output_dir: str | None = None
    target_key: TargetKey | None = None
    accidental_mode: AccidentalMode | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode | None = None
    jianpu_syntax_highlight: bool | None = None
    work_dir: str | None = None
    ocr_provider: str | None = None
    ocr_api_key: str | None = None
    ai_provider: str | None = None
    ai_api_key: str | None = None
    assistant_provider: str | None = None
    assistant_api_key: str | None = None
    omr_preprocess: bool | None = None
    omr_preprocess_long_edge: int | None = None
    omr_preprocess_binarize: bool | None = None


class CacheCleanupResponse(BaseModel):
    cache_dir: str
    before_bytes: int
    after_bytes: int
    freed_bytes: int
    removed_items: int
    preserved_uploads: int
