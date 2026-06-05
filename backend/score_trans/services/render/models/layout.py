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
    dynamic: str | None = None
    articulation: str | None = None
    articulations: list[str] = field(default_factory=list)
    ornaments: list[str] = field(default_factory=list)
    technical: list[str] = field(default_factory=list)


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
    errors: list[str] = field(default_factory=list)
