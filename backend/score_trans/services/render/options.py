from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode

from score_trans.config.settings import (
    RENDER_BEAT_GAP,
    RENDER_CHORD_GAP,
    RENDER_FONT,
    RENDER_LINE_HEIGHT,
    RENDER_MARGIN,
    RENDER_MAX_MEASURE_WIDTH,
    RENDER_MEASURE_WIDTH,
    RENDER_MIN_MEASURE_WIDTH,
    RENDER_SHOW_BEAT_GUIDES,
    RENDER_SHOW_MEASURE_NUMBERS,
    RENDER_SHOW_STAFF_GUIDES,
    RENDER_TITLE,
    RENDER_WIDTH,
)


@dataclass(slots=True)
class RenderOptions:
    title: str = RENDER_TITLE
    width: int = RENDER_WIDTH
    margin: int = RENDER_MARGIN
    measure_width: int = RENDER_MEASURE_WIDTH
    line_height: int = RENDER_LINE_HEIGHT
    font_family: str = RENDER_FONT
    min_measure_width: int = RENDER_MIN_MEASURE_WIDTH
    max_measure_width: int = RENDER_MAX_MEASURE_WIDTH
    beat_gap: int = RENDER_BEAT_GAP
    staff_space: float = 21.0
    note_min_gap: float = 9.0
    short_note_gap_ratio: float = 1.0
    short_note_slot_width_ratio: float = 1.0
    tuplet_gap_ratio: float = 0.16
    tuplet_slot_width_ratio: float = 0.54
    duration_spacing_ratio: float = 1.0
    chord_gap: float = float(RENDER_CHORD_GAP)
    chord_token_width: float = 42.0
    note_font_size: float = 30.0
    accidental_font_size: float = 18.0
    measure_number_font_size: float = 24.0
    measure_attribute_font_size: float = 18.0
    repeat_count_font_size: float = 22.0
    tuplet_font_size: float = 15.0
    lyric_font_size: float = 18.0
    dynamic_font_size: float = 22.0
    ornament_font_size: float = 15.0
    technical_font_size: float = 13.0
    technique_font_size: float = 16.0
    compact_measure_layout: bool = False
    show_beat_guides: bool = RENDER_SHOW_BEAT_GUIDES
    show_staff_guides: bool = RENDER_SHOW_STAFF_GUIDES
    show_measure_numbers: bool = RENDER_SHOW_MEASURE_NUMBERS
    measure_number_mode: MeasureNumberMode = "all"
