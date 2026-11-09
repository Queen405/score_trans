from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction

from ....models.common.errors import RenderError
from ....models.score import Event
from .geometry import VisualPart
from .style import PublicationStyle


@dataclass(frozen=True, slots=True)
class SpacingItem:
    event: Event
    parts: tuple[VisualPart, ...]

    @property
    def start(self) -> Fraction:
        return self.event.start or Fraction(0)


@dataclass(frozen=True, slots=True)
class SpacingLane:
    items: tuple[SpacingItem, ...]
    boundaries: tuple[Fraction, ...] = ()
    rhythmic: bool = True


@dataclass(frozen=True, slots=True)
class MeasureSpacing:
    """One feasible hard/natural profile used by measurement and every renderer."""

    times: tuple[Fraction, ...]
    hard: tuple[float, ...]
    natural: tuple[float, ...]
    weights: tuple[float, ...]

    @property
    def minimum_width(self) -> float:
        return self.hard[-1]

    @property
    def natural_width(self) -> float:
        return self.natural[-1]

    def positions(self, left: float, right: float) -> dict[Fraction, float]:
        available = right - left
        if available < self.minimum_width - 1e-6:
            raise RenderError("小节符号超出可用宽度；请减少每行小节数或调整字号")
        if available < self.natural_width:
            elastic = self.natural_width - self.minimum_width
            scale = (available - self.minimum_width) / elastic if elastic > 0 else 0.0
            coordinates = [
                hard + scale * (natural - hard)
                for hard, natural in zip(self.hard, self.natural, strict=True)
            ]
        else:
            spare = available - self.natural_width
            weight_sum = sum(self.weights) or 1.0
            cumulative = 0.0
            coordinates = [0.0]
            for index, weight in enumerate(self.weights, 1):
                cumulative += weight
                coordinates.append(
                    self.natural[index] + spare * cumulative / weight_sum
                )
        # Index zero is the left boundary; the final time is the right boundary.
        return {
            time: left + coordinates[index + 1]
            for index, time in enumerate(self.times[:-1])
        }


def duration_spring(
    duration: Fraction, shortest: Fraction, style: PublicationStyle
) -> float:
    if duration <= 0 or shortest <= 0:
        return 0.0
    ratio = float(duration / shortest)
    if ratio >= 1:
        return style.minimum_event_gap + style.spacing_increment * math.log2(ratio)
    return max(0.0, style.minimum_event_gap * ratio)


def _collision_distance(
    left: SpacingItem, right: SpacingItem, clearance: float
) -> float:
    return max(
        (
            a.ink_box.right - b.ink_box.left + clearance
            for a in left.parts
            for b in right.parts
            if a.role != "rhythm-edge"
            and b.role != "rhythm-edge"
            and a.ink_box.top < b.ink_box.bottom + clearance
            and b.ink_box.top < a.ink_box.bottom + clearance
        ),
        default=0.0,
    )


def measure_spacing(
    lanes: tuple[SpacingLane, ...],
    duration: Fraction,
    style: PublicationStyle,
    *,
    common_shortest: Fraction | None = None,
) -> MeasureSpacing:
    items = [item for lane in lanes for item in lane.items]
    end = max([duration, *(item.start + item.event.duration for item in items)])
    end = max(end, Fraction(1, 64))
    times = sorted({Fraction(0), end, *(item.start for item in items)})
    indices = {time: index + 1 for index, time in enumerate(times)}
    end_index = indices[end]
    edges: dict[tuple[int, int], float] = {}

    def constrain(start: int, stop: int, distance: float) -> None:
        if stop > start:
            key = (start, stop)
            edges[key] = max(edges.get(key, 0.0), distance)

    for index in range(end_index):
        constrain(index, index + 1, 0.0)
    for item in items:
        index = indices[item.start]
        left_ink = min((part.ink_box.left for part in item.parts), default=0.0)
        right_ink = max((part.ink_box.right for part in item.parts), default=0.0)
        constrain(0, index, style.event_clearance - left_ink)
        constrain(index, end_index, right_ink + style.event_clearance)
    for lane in lanes:
        ordered = sorted(lane.items, key=lambda item: item.start)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1 :]:
                constrain(
                    indices[first.start],
                    indices[second.start],
                    _collision_distance(first, second, style.event_clearance),
                )

    tuplet_ranges: set[tuple[int, int]] = set()
    for lane in lanes:
        groups: dict[str, list[int]] = {}
        for item in lane.items:
            if item.event.tuplet_id:
                groups.setdefault(item.event.tuplet_id, []).append(indices[item.start])
        tuplet_ranges.update(
            (min(group), max(group)) for group in groups.values() if len(group) > 1
        )

    def solve(requirements: dict[tuple[int, int], float]) -> tuple[float, ...]:
        requirements = dict(requirements)
        for _ in range(max(1, end_index * (len(tuplet_ranges) + 1))):
            incoming: list[list[tuple[int, float]]] = [[] for _ in range(end_index + 1)]
            for (start, stop), distance in requirements.items():
                incoming[stop].append((start, distance))
            positions = [0.0] * (end_index + 1)
            for stop in range(1, end_index + 1):
                positions[stop] = max(
                    (positions[start] + distance for start, distance in incoming[stop]),
                    default=0.0,
                )
            changed = False
            for first, last in sorted(tuplet_ranges):
                slope = max(
                    (positions[index + 1] - positions[index])
                    / float(times[index] - times[index - 1])
                    for index in range(first, last)
                )
                for index in range(first, last):
                    distance = slope * float(times[index] - times[index - 1])
                    key = (index, index + 1)
                    if distance > requirements.get(key, 0.0) + 1e-6:
                        requirements[key] = distance
                        changed = True
            if not changed:
                return tuple(positions)
        raise RenderError("连音组间距约束无法收敛，请检查连音时值")

    hard = solve(edges)
    natural_edges = dict(edges)
    durations = [
        item.event.duration
        for lane in lanes
        if lane.rhythmic
        for item in lane.items
        if item.event.duration > 0
    ]
    counts = Counter(durations)
    shortest = common_shortest or (
        min(min(counts, key=lambda value: (-counts[value], value)), Fraction(1, 2))
        if counts
        else Fraction(1, 2)
    )
    beat_crossings: set[Fraction] = set()
    for lane in lanes:
        if not lane.rhythmic:
            continue
        for boundary, following in zip(lane.boundaries, lane.boundaries[1:]):
            group = [item for item in lane.items if boundary <= item.start < following]
            if len(group) > 1:
                beat_crossings.add(following)

    weights = [0.0]
    mixed_subdivisions = len({b - a for a, b in zip(times, times[1:])}) > 1
    for start, stop in zip(times, times[1:]):
        delta = stop - start
        spring = duration_spring(delta, shortest, style)
        # Spacing belongs to elapsed musical time, including rests. Looking
        # only at pitched pairs makes an eighth rest receive several times
        # the space of an equal-duration note under the compact default.
        short = delta <= Fraction(1, 2)
        same_tuplet = any(
            first <= indices[start] < indices[stop] <= last
            for first, last in tuplet_ranges
        )
        if same_tuplet:
            spring = max(18.0, style.minimum_event_gap * 0.72)
        elif short:
            spring *= style.short_note_gap_scale
        # Uniform subdivisions keep exact common beat midpoints. The visible
        # division is already carried by the beam break; mixed rhythms may ask
        # for a small optical gap, which remains elastic.
        extra = (
            min(style.beat_boundary_gap, spring * style.beat_boundary_ratio)
            if (
                mixed_subdivisions
                and stop in beat_crossings
                and stop != end
                and not same_tuplet
            )
            else 0.0
        )
        key = (indices[start], indices[stop])
        natural_edges[key] = max(edges.get(key, 0.0), spring) + extra
        weights.append(max(1e-6, spring))
    natural = solve(natural_edges)
    # Stretch must preserve tuplet ratios too, including additional time columns
    # introduced by another voice inside a tuplet's own subdivisions.
    for _ in range(len(tuplet_ranges) + 1):
        changed = False
        for first, last in sorted(tuplet_ranges):
            slope = max(
                weights[index] / float(times[index] - times[index - 1])
                for index in range(first, last)
            )
            for index in range(first, last):
                weight = slope * float(times[index] - times[index - 1])
                if weight > weights[index] + 1e-6:
                    weights[index] = weight
                    changed = True
        if not changed:
            break
    # No space is added before the first beat; all free space belongs to time.
    return MeasureSpacing(tuple(times), hard, natural, tuple(weights))
