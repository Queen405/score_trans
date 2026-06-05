# noqa: D100
from __future__ import annotations

# Compatibility re-exports for legacy imports.
# New code should import from score_trans.services.ai.transcription.
from .transcription import (
    AiTranscriptionResult,
    AiTranscriptionService,
    PreparedScorePage,
    TranscribedScorePage,
    clean_jianpu_text,
    ensure_jianpu_header,
    extract_header,
    first_present,
    merge_page_jianpu_texts,
    normalize_key_value,
    normalize_meter_value,
    prepare_score_pages,
    strip_header,
    validate_jianpu_text,
)

__all__ = [
    "AiTranscriptionService",
    "AiTranscriptionResult",
    "PreparedScorePage",
    "TranscribedScorePage",
    "prepare_score_pages",
    "clean_jianpu_text",
    "ensure_jianpu_header",
    "normalize_key_value",
    "normalize_meter_value",
    "validate_jianpu_text",
    "merge_page_jianpu_texts",
    "extract_header",
    "strip_header",
    "first_present",
]
