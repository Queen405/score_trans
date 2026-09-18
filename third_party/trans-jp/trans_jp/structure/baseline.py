from __future__ import annotations

import numpy as np
from ..models.geometry import Curve
from ..models.raster import SymbolCandidate, RowGeometry


def fit_bands(candidates: tuple[SymbolCandidate, ...]) -> tuple[RowGeometry, ...]:
    glyphs = [
        c
        for c in candidates
        if c.bounds.height >= 5
        and 0.15 <= c.bounds.width / max(c.bounds.height, 1) <= 1.5
        and c.area / (c.bounds.width * c.bounds.height) >= 0.15
    ]
    groups: list[list[SymbolCandidate]] = []
    for candidate in sorted(glyphs, key=lambda c: c.bounds.bottom):
        b = candidate.bounds
        group = next(
            (
                g
                for g in groups
                if abs(float(np.median([v.bounds.bottom for v in g])) - b.bottom)
                <= 0.45 * float(np.median([v.bounds.height for v in g]))
            ),
            None,
        )
        if group is None:
            groups.append([candidate])
        else:
            group.append(candidate)
    result = []
    for group in groups:
        group.sort(key=lambda c: c.bounds.cx)
        h = float(np.median([c.bounds.height for c in group]))
        # Octave dots can share a nearby baseline but must never become digit
        # candidates merely because their horizontal prior is closer.
        group = [c for c in group if c.bounds.height >= h * 0.55]
        if not group:
            continue
        # Piecewise medians follow slow page curvature without snapping to an
        # individual accidental, octave dot or unusually tall digit.
        chunks = np.array_split(np.arange(len(group)), max(1, len(group) // 5))
        points = []
        for chunk in chunks:
            points.append(
                (
                    float(np.median([group[i].bounds.cx for i in chunk])),
                    float(np.median([group[i].bounds.bottom for i in chunk])),
                )
            )
        if len(points) == 1:
            points = [
                (group[0].bounds.x, points[0][1]),
                (group[-1].bounds.right, points[0][1]),
            ]
        baseline = Curve(tuple(points))
        result.append(
            RowGeometry(
                Curve(tuple((x, y - h) for x, y in points)),
                baseline,
                baseline,
                h,
                tuple(group),
            )
        )
    return tuple(result)
