from __future__ import annotations

from score_trans.config.settings import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_PROVIDER,
    ASSISTANT_API_KEY,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
    ASSISTANT_PROVIDER,
    AUDIVERIS_MAX_HEAP,
    AUDIVERIS_MAX_PIXEL_COUNT,
    AUDIVERIS_PATH,
    JAVA_HOME,
    OCR_API_KEY,
    OCR_BASE_URL,
    OCR_FALLBACK_MODEL,
    OCR_MODEL,
    OCR_PROVIDER,
    OUTPUT_DIR,
)

from ...dao.settings.settings_dao import SettingsDao


def settings_defaults() -> dict[str, str]:
    return {
        "audiveris_path": AUDIVERIS_PATH,
        "java_home": JAVA_HOME,
        "audiveris_max_heap": AUDIVERIS_MAX_HEAP,
        "audiveris_max_pixel_count": AUDIVERIS_MAX_PIXEL_COUNT,
        "output_dir": OUTPUT_DIR,
        "target_key": "C",
        "midi_tempo": "auto",
        "show_measure_numbers": "1",
        "measure_number_mode": "all",
        "confirm_start_measure_number": "1",
        "jianpu_syntax_highlight": "0",
        "accidental_mode": "auto",
        "ocr_provider": OCR_PROVIDER,
        "ocr_api_key": OCR_API_KEY,
        "ocr_base_url": OCR_BASE_URL,
        "ocr_model": OCR_MODEL,
        "ocr_fallback_model": OCR_FALLBACK_MODEL,
        "ai_provider": AI_PROVIDER,
        "ai_api_key": AI_API_KEY,
        "ai_base_url": AI_BASE_URL,
        "ai_model": AI_MODEL,
        "assistant_provider": ASSISTANT_PROVIDER,
        "assistant_api_key": ASSISTANT_API_KEY,
        "assistant_base_url": ASSISTANT_BASE_URL,
        "assistant_model": ASSISTANT_MODEL,
    }


def configured_settings_dao() -> SettingsDao:
    return SettingsDao.default(settings_defaults())
