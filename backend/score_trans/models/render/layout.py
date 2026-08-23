from __future__ import annotations

from pydantic import BaseModel, Field

PUBLICATION_ENGINE_VERSION = "publication-5"
DEFAULT_CONTENT_SCALE_PERCENT = 67
DEFAULT_SYSTEM_GAP_PERCENT = 92
DEFAULT_SHORT_NOTE_GAP_PERCENT = 90


class A4LayoutRequest(BaseModel):
    jianpu_content_scale_percent: int = Field(
        default=DEFAULT_CONTENT_SCALE_PERCENT, ge=65, le=100
    )
    jianpu_system_gap_percent: int = Field(
        default=DEFAULT_SYSTEM_GAP_PERCENT, ge=80, le=120
    )
    jianpu_short_note_gap_percent: int = Field(
        default=DEFAULT_SHORT_NOTE_GAP_PERCENT, ge=80, le=120
    )


def a4_layout_key(
    content_scale_percent: int,
    system_gap_percent: int,
    short_note_gap_percent: int,
) -> str:
    return f"{content_scale_percent}:{system_gap_percent}:{short_note_gap_percent}"
