from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from .geometry import Box, Point, Curve

Orientation = Literal["horizontal", "vertical"]


@dataclass(frozen=True, slots=True)
class Run:
    coordinate: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Section:
    orientation: Orientation
    runs: tuple[Run, ...]
    bounds: Box
    area: int


@dataclass(frozen=True, slots=True)
class Filament:
    orientation: Orientation
    points: tuple[Point, Point]
    thickness: float
    support: float
    bounds: Box

    @property
    def slope(self) -> float:
        a, b = self.points
        dx, dy = b[0] - a[0], b[1] - a[1]
        return (
            dy / dx
            if self.orientation == "horizontal" and dx
            else dx / dy
            if dy
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class SymbolCandidate:
    candidate_id: str
    kind: str
    bounds: Box
    area: int


@dataclass(frozen=True, slots=True)
class RowGeometry:
    top: Curve
    baseline: Curve
    bottom: Curve
    digit_height: float
    candidates: tuple[SymbolCandidate, ...]


@dataclass(frozen=True, slots=True)
class RowAnalysis:
    components: tuple[SymbolCandidate, ...]
    horizontal: tuple[Filament, ...]
    vertical: tuple[Filament, ...]
    bands: tuple[RowGeometry, ...]
    line_thickness: float
