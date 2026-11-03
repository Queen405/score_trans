from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode
from score_trans.models.render.layout import (
    DEFAULT_BEAT_GAP_PERCENT,
    DEFAULT_BREAK_BEAMS_AT_BEAT,
    DEFAULT_CONTENT_SCALE_PERCENT,
    DEFAULT_MEASURES_PER_SYSTEM,
    DEFAULT_MARGIN_TOP_MM,
    DEFAULT_MARGIN_BOTTOM_MM,
    DEFAULT_MARGIN_LEFT_MM,
    DEFAULT_MARGIN_RIGHT_MM,
    DEFAULT_HEADER_GAP_MM,
    DEFAULT_FOOTER_PROTECTION_MM,
    DEFAULT_NOTE_SIZE_PERCENT,
    DEFAULT_LYRIC_SIZE_PERCENT,
    DEFAULT_TITLE_SIZE_PERCENT,
    DEFAULT_ANNOTATION_SIZE_PERCENT,
    DEFAULT_SHORT_NOTE_GAP_PERCENT,
    DEFAULT_SYSTEM_GAP_PERCENT,
    MAX_BEAT_GAP_PERCENT,
    MAX_CONTENT_SCALE_PERCENT,
    MAX_MARGIN_MM,
    MAX_NOTE_SIZE_PERCENT,
    MAX_LYRIC_SIZE_PERCENT,
    MAX_TITLE_SIZE_PERCENT,
    MAX_ANNOTATION_SIZE_PERCENT,
    MAX_HEADER_GAP_MM,
    MAX_FOOTER_PROTECTION_MM,
    MAX_SHORT_NOTE_GAP_PERCENT,
    MAX_SYSTEM_GAP_PERCENT,
    MIN_BEAT_GAP_PERCENT,
    MIN_CONTENT_SCALE_PERCENT,
    MIN_PAGE_MM,
    MIN_NOTE_SIZE_PERCENT,
    MIN_LYRIC_SIZE_PERCENT,
    MIN_TITLE_SIZE_PERCENT,
    MIN_ANNOTATION_SIZE_PERCENT,
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

    title: str | None = None
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
    show_title: bool = True
    show_page_number: bool = True
    break_beams_at_beat: bool = DEFAULT_BREAK_BEAMS_AT_BEAT


@dataclass(frozen=True, slots=True)
class A4LayoutOptions:
    content_scale_percent: int = DEFAULT_CONTENT_SCALE_PERCENT
    system_gap_percent: int = DEFAULT_SYSTEM_GAP_PERCENT
    short_note_gap_percent: int = DEFAULT_SHORT_NOTE_GAP_PERCENT
    beat_gap_percent: int = DEFAULT_BEAT_GAP_PERCENT
    break_beams_at_beat: bool = DEFAULT_BREAK_BEAMS_AT_BEAT
    measures_per_system: int = DEFAULT_MEASURES_PER_SYSTEM
    margin_top_mm: float = DEFAULT_MARGIN_TOP_MM
    margin_bottom_mm: float = DEFAULT_MARGIN_BOTTOM_MM
    margin_left_mm: float = DEFAULT_MARGIN_LEFT_MM
    margin_right_mm: float = DEFAULT_MARGIN_RIGHT_MM
    header_gap_mm: float = DEFAULT_HEADER_GAP_MM
    footer_protection_mm: float = DEFAULT_FOOTER_PROTECTION_MM
    note_size_percent: int = DEFAULT_NOTE_SIZE_PERCENT
    lyric_size_percent: int = DEFAULT_LYRIC_SIZE_PERCENT
    title_size_percent: int = DEFAULT_TITLE_SIZE_PERCENT
    annotation_size_percent: int = DEFAULT_ANNOTATION_SIZE_PERCENT

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
        if (
            isinstance(self.measures_per_system, bool)
            or not isinstance(self.measures_per_system, int)
            or self.measures_per_system not in (0, 3, 4, 5)
        ):
            raise ValueError("measures_per_system must be one of 0, 3, 4, 5")
        page_ranges = (
            ("margin_top_mm", self.margin_top_mm, MAX_MARGIN_MM),
            ("margin_bottom_mm", self.margin_bottom_mm, MAX_MARGIN_MM),
            ("margin_left_mm", self.margin_left_mm, MAX_MARGIN_MM),
            ("margin_right_mm", self.margin_right_mm, MAX_MARGIN_MM),
            ("header_gap_mm", self.header_gap_mm, MAX_HEADER_GAP_MM),
            (
                "footer_protection_mm",
                self.footer_protection_mm,
                MAX_FOOTER_PROTECTION_MM,
            ),
        )
        for field, value, maximum in page_ranges:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field} must be numeric")
            if not MIN_PAGE_MM <= value <= maximum:
                raise ValueError(f"{field} must be between 0 and {maximum}")
        size_ranges = (
            (
                "note_size_percent",
                self.note_size_percent,
                MIN_NOTE_SIZE_PERCENT,
                MAX_NOTE_SIZE_PERCENT,
            ),
            (
                "lyric_size_percent",
                self.lyric_size_percent,
                MIN_LYRIC_SIZE_PERCENT,
                MAX_LYRIC_SIZE_PERCENT,
            ),
            (
                "title_size_percent",
                self.title_size_percent,
                MIN_TITLE_SIZE_PERCENT,
                MAX_TITLE_SIZE_PERCENT,
            ),
            (
                "annotation_size_percent",
                self.annotation_size_percent,
                MIN_ANNOTATION_SIZE_PERCENT,
                MAX_ANNOTATION_SIZE_PERCENT,
            ),
        )
        for field, value, minimum, maximum in size_ranges:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
            if not minimum <= value <= maximum:
                raise ValueError(f"{field} must be between {minimum} and {maximum}")
        for field, value, minimum, maximum in ranges:
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field} must be an integer")
            if not minimum <= value <= maximum:
                raise ValueError(f"{field} must be between {minimum} and {maximum}")

    @property
    def content_scale(self) -> float:
        return self.content_scale_percent / 100.0

    @property
    def note_size_scale(self) -> float:
        return self.note_size_percent / 100.0

    @property
    def lyric_size_scale(self) -> float:
        return self.lyric_size_percent / 100.0

    @property
    def title_size_scale(self) -> float:
        return self.title_size_percent / 100.0

    @property
    def annotation_size_scale(self) -> float:
        return self.annotation_size_percent / 100.0

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
            self.break_beams_at_beat,
            self.measures_per_system,
            ":".join(
                f"{value:g}"
                for value in (
                    self.margin_top_mm,
                    self.margin_bottom_mm,
                    self.margin_left_mm,
                    self.margin_right_mm,
                    self.header_gap_mm,
                    self.footer_protection_mm,
                    self.note_size_percent,
                    self.lyric_size_percent,
                    self.title_size_percent,
                    self.annotation_size_percent,
                )
            ),
        )
