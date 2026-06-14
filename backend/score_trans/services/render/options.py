from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode

from score_trans.config.settings import (
    RENDER_BEAT_GAP,
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
    show_beat_guides: bool = RENDER_SHOW_BEAT_GUIDES
    show_staff_guides: bool = RENDER_SHOW_STAFF_GUIDES
    show_measure_numbers: bool = RENDER_SHOW_MEASURE_NUMBERS
    measure_number_mode: MeasureNumberMode = "all"
