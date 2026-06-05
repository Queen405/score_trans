from __future__ import annotations

import re
from typing import Any

from ...models.score import OCRTextBlock


DEFAULT_OCR_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_OCR_MODEL = "deepseek-ai/DeepSeek-OCR"
DEFAULT_OCR_FALLBACK_MODEL = "Qwen/Qwen3-VL-8B-Instruct"


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
