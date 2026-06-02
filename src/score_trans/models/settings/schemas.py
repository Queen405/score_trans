from __future__ import annotations

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    audiveris_path: str
    java_home: str
    work_dir: str
    target_key: str = "C"
    output_dir: str = ""
    ocr_api_key: str = ""
    ocr_api_key_set: bool = False
    ocr_base_url: str = "https://api.siliconflow.cn/v1"
    ocr_model: str = "deepseek-ai/DeepSeek-OCR"
    omr_preprocess: bool = True
    omr_preprocess_long_edge: int = 3600
    omr_preprocess_binarize: bool = False


class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    java_home: str | None = None
    output_dir: str | None = None
    ocr_api_key: str | None = None
    ocr_base_url: str | None = None
    ocr_model: str | None = None
    omr_preprocess: bool | None = None
    omr_preprocess_long_edge: int | None = None
    omr_preprocess_binarize: bool | None = None

