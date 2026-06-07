from __future__ import annotations

from pydantic import BaseModel

from score_trans.config.settings import (
    AI_BASE_URL,
    AI_MODEL,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
    OCR_BASE_URL,
    OCR_MODEL,
    OMR_PREPROCESS,
    OMR_PREPROCESS_BINARIZE,
    OMR_PREPROCESS_LONG_EDGE,
)


class SettingsResponse(BaseModel):
    audiveris_path: str
    java_home: str
    work_dir: str
    target_key: str = "C"
    output_dir: str = ""
    ocr_api_key: str = ""
    ocr_api_key_set: bool = False
    ocr_base_url: str = OCR_BASE_URL
    ocr_model: str = OCR_MODEL
    ai_api_key: str = ""
    ai_api_key_set: bool = False
    ai_base_url: str = AI_BASE_URL
    ai_model: str = AI_MODEL
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
    target_key: str | None = None
    work_dir: str | None = None
    ocr_api_key: str | None = None
    ocr_base_url: str | None = None
    ocr_model: str | None = None
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    assistant_api_key: str | None = None
    assistant_base_url: str | None = None
    assistant_model: str | None = None
    omr_preprocess: bool | None = None
    omr_preprocess_long_edge: int | None = None
    omr_preprocess_binarize: bool | None = None
