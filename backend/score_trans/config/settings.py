from __future__ import annotations

import os

from score_trans.utils.env import load_project_env

# Load project .env once before reading any configuration variables.
load_project_env()


def _s(name: str) -> str:
    """Required string environment variable."""
    return os.environ[name]


def _s_or(name: str, default: str = "") -> str:
    """Optional string environment variable."""
    return os.getenv(name, default)


def _i(name: str) -> int:
    """Required integer environment variable."""
    return int(os.environ[name])


def _f(name: str) -> float:
    """Required float environment variable."""
    return float(os.environ[name])


def _i_or(name: str, default: int) -> int:
    """Optional integer environment variable."""
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _b(name: str) -> bool:
    """Required boolean environment variable."""
    return os.environ[name].lower() in ("1", "true", "yes", "on")


def _b_or(name: str, default: bool = False) -> bool:
    """Optional boolean environment variable."""
    fallback = "1" if default else "0"
    return os.getenv(name, fallback).lower() in ("1", "true", "yes", "on")


def _positive_i_or(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer byte count") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer byte count")
    return value


# API
API_TITLE: str = _s("SCORE_TRANS_API_TITLE")
API_VERSION: str = _s("SCORE_TRANS_API_VERSION")
CORS_ORIGINS: str = _s("SCORE_TRANS_CORS_ORIGINS")
API_AUTH_DISABLED: bool = _b_or("SCORE_TRANS_API_AUTH_DISABLED")
API_TOKEN: str = _s_or("SCORE_TRANS_API_TOKEN")
if not API_AUTH_DISABLED and len(API_TOKEN) < 32:
    raise ValueError(
        "SCORE_TRANS_API_TOKEN must contain at least 32 characters when "
        "SCORE_TRANS_API_AUTH_DISABLED is false"
    )
MAX_UPLOAD_FILE_BYTES: int = _positive_i_or(
    "SCORE_TRANS_MAX_UPLOAD_FILE_BYTES",
    256 * 1024 * 1024,
)
MAX_UPLOAD_REQUEST_BYTES: int = _positive_i_or(
    "SCORE_TRANS_MAX_UPLOAD_REQUEST_BYTES",
    512 * 1024 * 1024,
)

# Paths (optional, code provides fallbacks when empty)
AUDIVERIS_PATH: str = _s_or("SCORE_TRANS_AUDIVERIS")
WORK_DIR: str = _s_or("SCORE_TRANS_WORKDIR")
JAVA_HOME: str = _s_or("SCORE_TRANS_JAVA_HOME")

# Audiveris / Java OMR command options
AUDIVERIS_STEP: str = _s_or("SCORE_TRANS_AUDIVERIS_STEP")
AUDIVERIS_FORCE: bool = _b_or("SCORE_TRANS_AUDIVERIS_FORCE")
AUDIVERIS_SAVE: bool = _b_or("SCORE_TRANS_AUDIVERIS_SAVE", True)
AUDIVERIS_SWAP: bool = _b_or("SCORE_TRANS_AUDIVERIS_SWAP")
AUDIVERIS_TRANSCRIBE: bool = _b_or("SCORE_TRANS_AUDIVERIS_TRANSCRIBE")
AUDIVERIS_SHEETS: str = _s_or("SCORE_TRANS_AUDIVERIS_SHEETS")
AUDIVERIS_CONSTANTS: str = _s_or("SCORE_TRANS_AUDIVERIS_CONSTANTS")
AUDIVERIS_EXTRA_ARGS: str = _s_or("SCORE_TRANS_AUDIVERIS_EXTRA_ARGS")
AUDIVERIS_MAX_HEAP: str = _s_or("SCORE_TRANS_AUDIVERIS_MAX_HEAP", "3g")
AUDIVERIS_MAX_PIXEL_COUNT: str = _s_or(
    "SCORE_TRANS_AUDIVERIS_MAX_PIXEL_COUNT", "4500000"
)
AUDIVERIS_AUTO_UPSCALE: bool = _b_or("SCORE_TRANS_AUDIVERIS_AUTO_UPSCALE", True)
AUDIVERIS_MIN_IMAGE_EDGE: int = _i_or("SCORE_TRANS_AUDIVERIS_MIN_IMAGE_EDGE", 2500)

# AI
AI_PROVIDER: str = _s("SCORE_TRANS_AI_PROVIDER")
AI_PROVIDER_PROFILES: str = _s("SCORE_TRANS_AI_PROVIDER_PROFILES")
AI_BASE_URL: str = _s("SCORE_TRANS_AI_BASE_URL")
AI_MODEL: str = _s("SCORE_TRANS_AI_MODEL")
AI_API_KEY: str = _s_or("SCORE_TRANS_AI_API_KEY")
AI_TIMEOUT: float = _f("SCORE_TRANS_AI_TIMEOUT")
AI_TEMPERATURE: float = _f("SCORE_TRANS_AI_TEMPERATURE")
AI_SYSTEM_MSG: str = _s_or("SCORE_TRANS_AI_SYSTEM_MSG")

# Workbench AI assistant
ASSISTANT_PROVIDER: str = _s("SCORE_TRANS_ASSISTANT_PROVIDER")
ASSISTANT_PROVIDER_PROFILES: str = _s("SCORE_TRANS_ASSISTANT_PROVIDER_PROFILES")
ASSISTANT_BASE_URL: str = _s("SCORE_TRANS_ASSISTANT_BASE_URL")
ASSISTANT_MODEL: str = _s("SCORE_TRANS_ASSISTANT_MODEL")
ASSISTANT_API_KEY: str = _s_or("SCORE_TRANS_ASSISTANT_API_KEY")
# 输出 token 上限：provider profile 的 max_tokens 优先，本变量为回退，再回退 4096。
ASSISTANT_MAX_TOKENS: int = _positive_i_or(
    "SCORE_TRANS_ASSISTANT_MAX_TOKENS",
    4096,
)

# AI 视觉转写输出 token 上限：provider profile 的 max_tokens 优先，本变量为回退，再回退 4096。
AI_MAX_TOKENS: int = _positive_i_or(
    "SCORE_TRANS_AI_MAX_TOKENS",
    4096,
)

# OCR
OCR_PROVIDER: str = _s("SCORE_TRANS_OCR_PROVIDER")
OCR_PROVIDER_PROFILES: str = _s("SCORE_TRANS_OCR_PROVIDER_PROFILES")
OCR_BASE_URL: str = _s("SCORE_TRANS_OCR_BASE_URL")
OCR_MODEL: str = _s("SCORE_TRANS_OCR_MODEL")
OCR_FALLBACK_MODEL: str = _s("SCORE_TRANS_OCR_FALLBACK_MODEL")
OCR_API_KEY: str = _s_or("SCORE_TRANS_OCR_API_KEY")
OCR_TIMEOUT: float = _f("SCORE_TRANS_OCR_TIMEOUT")
OCR_MAX_TOKENS: int = _i("SCORE_TRANS_OCR_MAX_TOKENS")
OCR_TEMPERATURE: float = _f("SCORE_TRANS_OCR_TEMPERATURE")

# PDF
PDF_RENDER_DPI: int = _i("SCORE_TRANS_PDF_RENDER_DPI")
UPLOAD_PDF_DPI: int = _i("SCORE_TRANS_UPLOAD_PDF_DPI")

# MIDI
MIDI_TICKS_PER_BEAT: int = _i("SCORE_TRANS_MIDI_TICKS_PER_BEAT")
MIDI_DEFAULT_VELOCITY: int = _i("SCORE_TRANS_MIDI_DEFAULT_VELOCITY")
