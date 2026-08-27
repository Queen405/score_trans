from __future__ import annotations

from pydantic import BaseModel, Field

PUBLICATION_ENGINE_VERSION = "publication-10"
DEFAULT_CONTENT_SCALE_PERCENT = 67
DEFAULT_SYSTEM_GAP_PERCENT = 92
DEFAULT_SHORT_NOTE_GAP_PERCENT = 90
MIN_CONTENT_SCALE_PERCENT = 65
MAX_CONTENT_SCALE_PERCENT = 100
MIN_SYSTEM_GAP_PERCENT = 20
MAX_SYSTEM_GAP_PERCENT = 180
MIN_SHORT_NOTE_GAP_PERCENT = 20
MAX_SHORT_NOTE_GAP_PERCENT = 180


class A4LayoutRequest(BaseModel):
    jianpu_content_scale_percent: int = Field(
        default=DEFAULT_CONTENT_SCALE_PERCENT,
        ge=MIN_CONTENT_SCALE_PERCENT,
        le=MAX_CONTENT_SCALE_PERCENT,
    )
    jianpu_system_gap_percent: int = Field(
        default=DEFAULT_SYSTEM_GAP_PERCENT,
        ge=MIN_SYSTEM_GAP_PERCENT,
        le=MAX_SYSTEM_GAP_PERCENT,
    )
    jianpu_short_note_gap_percent: int = Field(
        default=DEFAULT_SHORT_NOTE_GAP_PERCENT,
        ge=MIN_SHORT_NOTE_GAP_PERCENT,
        le=MAX_SHORT_NOTE_GAP_PERCENT,
    )


def a4_layout_key(
    content_scale_percent: int,
    system_gap_percent: int,
    short_note_gap_percent: int,
) -> str:
    return f"{content_scale_percent}:{system_gap_percent}:{short_note_gap_percent}"
