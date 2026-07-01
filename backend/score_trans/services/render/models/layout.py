from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any


@dataclass(slots=True)
class RenderItem:
    token: str
    duration: Fraction
    generated: bool = False
    start: Fraction | None = None
    lyric: str | None = None
    tie_start: bool = False
    tie_stop: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    slide_start: bool = False
    slide_stop: bool = False
    slide_direction: str | None = None
    dynamic: str | None = None
    articulation: str | None = None
    articulations: list[str] = field(default_factory=list)
    ornaments: list[str] = field(default_factory=list)
    technical: list[str] = field(default_factory=list)
    playback_index: int | None = None
    tuplet_id: str | None = None
    tuplet_count: int | None = None
    tuplet_index: int | None = None
    tuplet_start: bool = False
    tuplet_stop: bool = False
    source_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BeatLayout:
    items: list[RenderItem]
    width: float


@dataclass(slots=True)
class MeasureLayout:
    source: Any
    number: str | int
    beats: list[BeatLayout]
    width: float
    min_width: float = 0.0
    ideal_width: float = 0.0
    complexity: float = 1.0
    errors: list[str] = field(default_factory=list)
