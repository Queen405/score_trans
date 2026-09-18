from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    def union(self, other: Box) -> Box:
        left, top = min(self.x, other.x), min(self.y, other.y)
        return Box(
            left,
            top,
            max(self.right, other.right) - left,
            max(self.bottom, other.bottom) - top,
        )

    def clip(self, width: float, height: float) -> Box:
        left, top = max(0.0, min(self.x, width)), max(0.0, min(self.y, height))
        return Box(
            left,
            top,
            max(0.0, min(width, self.right) - left),
            max(0.0, min(height, self.bottom) - top),
        )


@dataclass(frozen=True, slots=True)
class Curve:
    points: tuple[Point, ...]

    def y_at(self, x: float) -> float:
        if not self.points:
            return 0.0
        if x <= self.points[0][0]:
            return self.points[0][1]
        for (ax, ay), (bx, by) in zip(self.points, self.points[1:]):
            if x <= bx:
                return ay + (by - ay) * (x - ax) / max(bx - ax, 1e-9)
        return self.points[-1][1]


@dataclass(frozen=True, slots=True)
class Transform:
    """Working image = scaled source sheared vertically by -slope * x."""

    scale_x: float = 1.0
    scale_y: float = 1.0
    slope: float = 0.0
    offset_y: float = 0.0

    def point(self, x: float, y: float) -> Point:
        return x / self.scale_x, (y + self.slope * x - self.offset_y) / self.scale_y

    def box(self, box: Box) -> Box:
        pts = [
            self.point(x, y) for x in (box.x, box.right) for y in (box.y, box.bottom)
        ]
        xs, ys = zip(*pts)
        return Box(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


@dataclass(frozen=True, slots=True)
class Primitive:
    kind: Literal["glyph", "dot", "line", "curve"]
    bounds: Box
    value: str = ""
    points: tuple[Point, ...] = ()
    thickness: float = 1.0
    hit_bounds: Box | None = None


@dataclass(slots=True)
class TokenGeometry:
    status: Literal["matched", "partial", "unmatched", "ignored", "unsupported"] = (
        "unmatched"
    )
    voice: int = 0
    bodies: list[Box] = field(default_factory=list)
    primitives: list[Primitive] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def bounds(self) -> Box | None:
        boxes = [p.hit_bounds or p.bounds for p in self.primitives]
        if not boxes:
            return None
        result = boxes[0]
        for box in boxes[1:]:
            result = result.union(box)
        return result
