from __future__ import annotations

from .protocols import OCRProvider, OCRRequest
from .text import infer_text_role, normalize_text_role
from .utils import (
    DEFAULT_OCR_BASE_URL,
    DEFAULT_OCR_FALLBACK_MODEL,
    DEFAULT_OCR_MODEL,
    _font_size_from_raw,
    _ocr_blocks_are_useful,
    is_deepseek_ocr_model,
    persisted_ocr_settings,
)

__all__ = [
    "OCRProvider",
    "OCRRequest",
    "infer_text_role",
    "normalize_text_role",
    "is_deepseek_ocr_model",
    "_ocr_blocks_are_useful",
    "_font_size_from_raw",
    "persisted_ocr_settings",
    "DEFAULT_OCR_BASE_URL",
    "DEFAULT_OCR_MODEL",
    "DEFAULT_OCR_FALLBACK_MODEL",
]
