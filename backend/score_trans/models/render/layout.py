from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

PUBLICATION_ENGINE_VERSION = "publication-29"
DEFAULT_CONTENT_SCALE_PERCENT = 88
DEFAULT_SYSTEM_GAP_PERCENT = 40
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
A4_UNITS_PER_MM = 1240.0 / 210.0
DEFAULT_MARGIN_TOP_MM = 8.0
DEFAULT_MARGIN_BOTTOM_MM = 5.0
DEFAULT_MARGIN_LEFT_MM = 10.0
DEFAULT_MARGIN_RIGHT_MM = 10.0
DEFAULT_HEADER_GAP_MM = 3.0
DEFAULT_FOOTER_PROTECTION_MM = 2.0
DEFAULT_NOTE_SIZE_PERCENT = 100
DEFAULT_LYRIC_SIZE_PERCENT = 100
DEFAULT_TITLE_SIZE_PERCENT = 100
DEFAULT_ANNOTATION_SIZE_PERCENT = 100
DEFAULT_PART_GAP_PERCENT = 75
DEFAULT_VOICE_GAP_PERCENT = 80
DEFAULT_LYRIC_LINE_GAP_PERCENT = 90
DEFAULT_LYRIC_NOTE_GAP_PERCENT = 90
MIN_VERTICAL_GAP_PERCENT = 50
MIN_PART_GAP_PERCENT = 0
MAX_VERTICAL_GAP_PERCENT = 200
MIN_NOTE_SIZE_PERCENT = 70
MAX_NOTE_SIZE_PERCENT = 140
MIN_LYRIC_SIZE_PERCENT = 60
MAX_LYRIC_SIZE_PERCENT = 150
MIN_TITLE_SIZE_PERCENT = 60
MAX_TITLE_SIZE_PERCENT = 160
MIN_ANNOTATION_SIZE_PERCENT = 60
MAX_ANNOTATION_SIZE_PERCENT = 150
MIN_PAGE_MM = 0.0
MAX_MARGIN_MM = 50.0
MAX_HEADER_GAP_MM = 30.0
MAX_FOOTER_PROTECTION_MM = 30.0
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
    jianpu_margin_top_mm: float = Field(default=DEFAULT_MARGIN_TOP_MM, ge=0, le=50)
    jianpu_margin_bottom_mm: float = Field(
        default=DEFAULT_MARGIN_BOTTOM_MM, ge=0, le=50
    )
    jianpu_margin_left_mm: float = Field(default=DEFAULT_MARGIN_LEFT_MM, ge=0, le=50)
    jianpu_margin_right_mm: float = Field(default=DEFAULT_MARGIN_RIGHT_MM, ge=0, le=50)
    jianpu_header_gap_mm: float = Field(default=DEFAULT_HEADER_GAP_MM, ge=0, le=30)
    jianpu_footer_protection_mm: float = Field(
        default=DEFAULT_FOOTER_PROTECTION_MM, ge=0, le=30
    )
    jianpu_note_size_percent: int = Field(
        default=DEFAULT_NOTE_SIZE_PERCENT, ge=70, le=140
    )
    jianpu_lyric_size_percent: int = Field(
        default=DEFAULT_LYRIC_SIZE_PERCENT, ge=60, le=150
    )
    jianpu_title_size_percent: int = Field(
        default=DEFAULT_TITLE_SIZE_PERCENT, ge=60, le=160
    )
    jianpu_annotation_size_percent: int = Field(
        default=DEFAULT_ANNOTATION_SIZE_PERCENT, ge=60, le=150
    )
    jianpu_part_gap_percent: int = Field(
        default=DEFAULT_PART_GAP_PERCENT, ge=MIN_PART_GAP_PERCENT, le=200
    )
    jianpu_voice_gap_percent: int = Field(
        default=DEFAULT_VOICE_GAP_PERCENT, ge=50, le=200
    )
    jianpu_lyric_line_gap_percent: int = Field(
        default=DEFAULT_LYRIC_LINE_GAP_PERCENT, ge=50, le=200
    )
    jianpu_lyric_note_gap_percent: int = Field(
        default=DEFAULT_LYRIC_NOTE_GAP_PERCENT, ge=50, le=200
    )

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
    layout_extras: str = "",
) -> str:
    return (
        f"{content_scale_percent}:{system_gap_percent}"
        f":{short_note_gap_percent}:{beat_gap_percent}:{int(break_beams_at_beat)}"
        f":{measures_per_system or 'a'}"
        + (f":{layout_extras}" if layout_extras else "")
    )
