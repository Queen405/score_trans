from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class RenderOptions:
    title: str = os.getenv("SCORE_TRANS_RENDER_TITLE", "简谱")
    width: int = int(os.getenv("SCORE_TRANS_RENDER_WIDTH", "1600"))
    margin: int = int(os.getenv("SCORE_TRANS_RENDER_MARGIN", "72"))
    measure_width: int = int(os.getenv("SCORE_TRANS_RENDER_MEASURE_WIDTH", "330"))
    line_height: int = int(os.getenv("SCORE_TRANS_RENDER_LINE_HEIGHT", "180"))
    font_family: str = os.getenv("SCORE_TRANS_RENDER_FONT", "Microsoft YaHei, SimSun, Arial, sans-serif")
    min_measure_width: int = int(os.getenv("SCORE_TRANS_RENDER_MIN_MEASURE_WIDTH", "112"))
    max_measure_width: int = int(os.getenv("SCORE_TRANS_RENDER_MAX_MEASURE_WIDTH", "1100"))
    beat_gap: int = int(os.getenv("SCORE_TRANS_RENDER_BEAT_GAP", "14"))
    show_beat_guides: bool = os.getenv("SCORE_TRANS_RENDER_SHOW_BEAT_GUIDES", "0").lower() in ("1", "true", "yes", "on")
    show_staff_guides: bool = os.getenv("SCORE_TRANS_RENDER_SHOW_STAFF_GUIDES", "0").lower() in ("1", "true", "yes", "on")
    show_measure_numbers: bool = os.getenv("SCORE_TRANS_RENDER_SHOW_MEASURE_NUMBERS", "1").lower() in ("1", "true", "yes", "on")
