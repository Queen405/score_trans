from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode
from score_trans.models.render.layout import (
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    a4_layout_key,
)


@dataclass(slots=True)
class RenderOptions:
    """Public render options retained at the domain boundary.

    Defaults are versioned with the publication engine rather than assembled
    from the removed SCORE_TRANS_RENDER_* environment variables.
    """

    title: str = "简谱"
    width: int = 800
    margin: int = 36
    font_family: str = "ScoreTransNotoSerif"
    min_measure_width: int = 150
    note_min_gap: float = 28.0
    note_font_size: float = 30.0
    accidental_font_size: float = 18.0
    lyric_font_size: float = 18.0
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int | None = 1


@dataclass(frozen=True, slots=True)
class A4LayoutOptions:
    content_scale_percent: int = DEFAULT_CONTENT_SCALE_PERCENT
    system_gap_percent: int = DEFAULT_SYSTEM_GAP_PERCENT
    short_note_gap_percent: int = DEFAULT_SHORT_NOTE_GAP_PERCENT

    @property
    def content_scale(self) -> float:
        return self.content_scale_percent / 100.0

    @property
    def system_gap_scale(self) -> float:
        return self.system_gap_percent / 100.0

    @property
    def short_note_gap_scale(self) -> float:
        return self.short_note_gap_percent / 100.0

    @property
    def key(self) -> str:
        return a4_layout_key(
            self.content_scale_percent,
            self.system_gap_percent,
            self.short_note_gap_percent,
        )
