from __future__ import annotations

import re
from typing import Any

from score_trans.config.settings import (  # noqa: F401
    OCR_BASE_URL as DEFAULT_OCR_BASE_URL,
)
from score_trans.config.settings import (  # noqa: F401
    OCR_FALLBACK_MODEL as DEFAULT_OCR_FALLBACK_MODEL,
)
from score_trans.config.settings import OCR_MODEL as DEFAULT_OCR_MODEL  # noqa: F401

from score_trans.models.score import OCRTextBlock


def is_deepseek_ocr_model(model: str) -> bool:
    return model.lower().endswith("/deepseek-ocr") or model.lower() == "deepseek-ocr"


def _ocr_blocks_are_useful(blocks: list[OCRTextBlock]) -> bool:
    for block in blocks:
        text = block.text.strip()
        if not text or text in {"}", "{", "[]"}:
            continue
        if block.bbox is not None or re.search(r"[\w\u4e00-\u9fff]", text):
            return True
    return False


def persisted_ocr_settings() -> dict[str, str]:
    try:
        from ..settings.settings_service import SettingsService

        return SettingsService().get_all()
    except Exception:
        return {}


def _font_size_from_raw(raw: dict[str, Any]) -> float | None:
    value = raw.get("fontSize", raw.get("font_size"))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
