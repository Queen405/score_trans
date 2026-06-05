from __future__ import annotations

import os

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    audiveris_path: str
    java_home: str
    work_dir: str
    target_key: str = "C"
    output_dir: str = ""
    ocr_api_key: str = ""
    ocr_api_key_set: bool = False
    ocr_base_url: str = os.getenv("SCORE_TRANS_OCR_BASE_URL", "https://api.siliconflow.cn/v1")
    ocr_model: str = os.getenv("SCORE_TRANS_OCR_MODEL", "deepseek-ai/DeepSeek-OCR")
    ai_api_key: str = ""
    ai_api_key_set: bool = False
    ai_base_url: str = os.getenv("SCORE_TRANS_AI_BASE_URL", "https://api.siliconflow.cn/v1")
    ai_model: str = os.getenv("SCORE_TRANS_AI_MODEL", "Qwen/Qwen3-VL-8B-Instruct")
    omr_preprocess: bool = os.getenv("SCORE_TRANS_OMR_PREPROCESS", "1").lower() in ("1", "true", "yes", "on")
    omr_preprocess_long_edge: int = int(os.getenv("SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE", "3600"))
    omr_preprocess_binarize: bool = os.getenv("SCORE_TRANS_OMR_PREPROCESS_BINARIZE", "0").lower() in ("1", "true", "yes", "on")


class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    java_home: str | None = None
    output_dir: str | None = None
    ocr_api_key: str | None = None
    ocr_base_url: str | None = None
    ocr_model: str | None = None
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    omr_preprocess: bool | None = None
    omr_preprocess_long_edge: int | None = None
    omr_preprocess_binarize: bool | None = None
