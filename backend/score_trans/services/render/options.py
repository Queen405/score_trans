from __future__ import annotations

from dataclasses import dataclass

from score_trans.models.common.types import MeasureNumberMode


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
