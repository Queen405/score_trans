from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode


@dataclass(frozen=True, slots=True)
class A4RenderTheme:
    note_font_size: float = 30.0
    accidental_font_size: float = 18.0
    measure_number_font_size: float = 15.0
    measure_attribute_font_size: float = 15.0
    repeat_count_font_size: float = 15.0
    tuplet_font_size: float = 15.0
    lyric_font_size: float = 18.0
    dynamic_font_size: float = 15.0
    ornament_font_size: float = 15.0
    technical_font_size: float = 15.0
    technique_font_size: float = 15.0


A4_RENDER_THEME = A4RenderTheme()


@dataclass(slots=True)
class RenderOptions:
    """Public render options retained at the domain boundary.

    Defaults are versioned with the publication engine rather than assembled
    from the removed SCORE_TRANS_RENDER_* environment variables.
    """

    title: str = "简谱"
    width: int = 800
    margin: int = 36
    measure_width: int = 200
    line_height: int = 116
    font_family: str = "ScoreTransNotoSerif"
    min_measure_width: int = 150
    max_measure_width: int = 520
    beat_gap: int = 8
    staff_space: float = 21.0
    note_min_gap: float = 28.0
    short_note_gap_ratio: float = 0.7
    short_note_slot_width_ratio: float = 0.8
    tuplet_gap_ratio: float = 0.16
    tuplet_slot_width_ratio: float = 0.54
    duration_spacing_ratio: float = 1.0
    chord_gap: float = 25.0
    chord_token_width: float = 42.0
    note_font_size: float = 30.0
    accidental_font_size: float = 18.0
    measure_number_font_size: float = 15.0
    measure_attribute_font_size: float = 15.0
    repeat_count_font_size: float = 15.0
    tuplet_font_size: float = 15.0
    lyric_font_size: float = 18.0
    dynamic_font_size: float = 15.0
    ornament_font_size: float = 15.0
    technical_font_size: float = 15.0
    technique_font_size: float = 15.0
    compact_measure_layout: bool = False
    show_beat_guides: bool = False
    show_staff_guides: bool = False
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
