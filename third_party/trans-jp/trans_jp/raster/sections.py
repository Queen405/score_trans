from __future__ import annotations

from ..models.geometry import Box
from ..models.raster import Run, Section, Orientation


def join_sections(
    runs: tuple[Run, ...],
    orientation: Orientation = "horizontal",
    *,
    length_ratio: float | None = None,
) -> tuple[Section, ...]:
    """Adjacent overlapping runs, optionally split where thickness changes abruptly."""
    parents = list(range(len(runs)))

    def root(i: int) -> int:
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    previous: list[int] = []
    current: list[int] = []
    coordinate = -1
    pi = 0
    for i, run in enumerate(runs):
        if run.coordinate != coordinate:
            previous = current if run.coordinate == coordinate + 1 else []
            current = []
            coordinate = run.coordinate
            pi = 0
        while pi < len(previous) and runs[previous[pi]].end < run.start:
            pi += 1
        pj = pi
        while pj < len(previous) and runs[previous[pj]].start <= run.end:
            j = previous[pj]
            other = runs[j]
            ratio = max(run.end - run.start, other.end - other.start) / max(
                1, min(run.end - run.start, other.end - other.start)
            )
            if length_ratio is None or ratio <= length_ratio:
                parents[root(j)] = root(i)
            pj += 1
        current.append(i)
    groups: dict[int, list[Run]] = {}
    for i, run in enumerate(runs):
        groups.setdefault(root(i), []).append(run)
    sections = []
    for group in groups.values():
        a = min(r.start for r in group)
        b = max(r.end for r in group)
        lo = min(r.coordinate for r in group)
        hi = max(r.coordinate for r in group) + 1
        box = (
            Box(a, lo, b - a, hi - lo)
            if orientation == "horizontal"
            else Box(lo, a, hi - lo, b - a)
        )
        sections.append(
            Section(orientation, tuple(group), box, sum(r.end - r.start for r in group))
        )
    return tuple(sections)
