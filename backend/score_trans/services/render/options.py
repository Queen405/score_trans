from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode
from score_trans.models.render.layout import (
    DEFAULT_BEAT_GAP_PERCENT,
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    MAX_BEAT_GAP_PERCENT,
    MAX_CONTENT_SCALE_PERCENT,
    MAX_SHORT_NOTE_GAP_PERCENT,
    MAX_SYSTEM_GAP_PERCENT,
    MIN_BEAT_GAP_PERCENT,
    MIN_CONTENT_SCALE_PERCENT,
    MIN_SHORT_NOTE_GAP_PERCENT,
    MIN_SYSTEM_GAP_PERCENT,
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
    beat_gap_percent: int = DEFAULT_BEAT_GAP_PERCENT

    def __post_init__(self) -> None:
        ranges = (
            (
                "content_scale_percent",
                self.content_scale_percent,
                MIN_CONTENT_SCALE_PERCENT,
                MAX_CONTENT_SCALE_PERCENT,
            ),
            (
                "system_gap_percent",
                self.system_gap_percent,
                MIN_SYSTEM_GAP_PERCENT,
                MAX_SYSTEM_GAP_PERCENT,
            ),
            (
                "short_note_gap_percent",
                self.short_note_gap_percent,
                MIN_SHORT_NOTE_GAP_PERCENT,
                MAX_SHORT_NOTE_GAP_PERCENT,
            ),
            (
                "beat_gap_percent",
                self.beat_gap_percent,
                MIN_BEAT_GAP_PERCENT,
                MAX_BEAT_GAP_PERCENT,
            ),
        )
        for field, value, minimum, maximum in ranges:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
            if not minimum <= value <= maximum:
                raise ValueError(f"{field} must be between {minimum} and {maximum}")

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
    def beat_gap_scale(self) -> float:
        return self.beat_gap_percent / 100.0

    @property
    def key(self) -> str:
        return a4_layout_key(
            self.content_scale_percent,
            self.system_gap_percent,
            self.short_note_gap_percent,
            self.beat_gap_percent,
        )
