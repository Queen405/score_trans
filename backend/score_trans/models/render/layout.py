from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

PUBLICATION_ENGINE_VERSION = "publication-20"
DEFAULT_CONTENT_SCALE_PERCENT = 80
DEFAULT_SYSTEM_GAP_PERCENT = 50
DEFAULT_SHORT_NOTE_GAP_PERCENT = 20
DEFAULT_BEAT_GAP_PERCENT = 100
MIN_CONTENT_SCALE_PERCENT = 65
MAX_CONTENT_SCALE_PERCENT = 100
MIN_SYSTEM_GAP_PERCENT = 20
MAX_SYSTEM_GAP_PERCENT = 180
MIN_SHORT_NOTE_GAP_PERCENT = 20
MAX_SHORT_NOTE_GAP_PERCENT = 180
MIN_BEAT_GAP_PERCENT = 0
MAX_BEAT_GAP_PERCENT = 200
DEFAULT_BREAK_BEAMS_AT_BEAT = False
DEFAULT_MEASURES_PER_SYSTEM = 0
MeasuresPerSystem = Literal[0, 3, 4, 5]


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
    jianpu_beat_gap_percent: int = Field(
        default=DEFAULT_BEAT_GAP_PERCENT,
        ge=MIN_BEAT_GAP_PERCENT,
        le=MAX_BEAT_GAP_PERCENT,
    )
    jianpu_break_beams_at_beat: bool = DEFAULT_BREAK_BEAMS_AT_BEAT
    jianpu_measures_per_system: MeasuresPerSystem = DEFAULT_MEASURES_PER_SYSTEM

    @field_validator("jianpu_measures_per_system", mode="before")
    @classmethod
    def validate_measures_per_system(cls, value: object) -> object:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in (0, 3, 4, 5)
        ):
            raise ValueError("jianpu_measures_per_system must be one of 0, 3, 4, 5")
        return value


def a4_layout_key(
    content_scale_percent: int,
    system_gap_percent: int,
    short_note_gap_percent: int,
    beat_gap_percent: int = DEFAULT_BEAT_GAP_PERCENT,
    break_beams_at_beat: bool = DEFAULT_BREAK_BEAMS_AT_BEAT,
    measures_per_system: int = DEFAULT_MEASURES_PER_SYSTEM,
) -> str:
    return (
        f"{content_scale_percent}:{system_gap_percent}"
        f":{short_note_gap_percent}:{beat_gap_percent}:{int(break_beams_at_beat)}"
        f":{measures_per_system or 'a'}"
    )
