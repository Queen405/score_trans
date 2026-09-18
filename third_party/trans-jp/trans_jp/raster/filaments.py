from __future__ import annotations

import math
import numpy as np
from ..models.geometry import Box
from ..models.raster import Filament, Orientation
from .runs import scan_runs
from .sections import join_sections


def detect_filaments(
    binary: np.ndarray, orientation: Orientation, scale: float
) -> tuple[Filament, ...]:
    """Trace thin cross-direction runs, then join collinear fragments across small gaps.

    Scanning across a line exposes its thickness; abrupt thickness changes split
    sections at digit crossings instead of absorbing a whole connected component.
    """
    cross = "vertical" if orientation == "horizontal" else "horizontal"
    thickness = max(2.0, scale * 0.23)
    runs = tuple(r for r in scan_runs(binary, cross) if r.end - r.start <= thickness)
    fragments = []
    for section in join_sections(runs, cross, length_ratio=2.5):
        coords = np.array([r.coordinate for r in section.runs], dtype=float)
        centers = np.array([(r.start + r.end) / 2 for r in section.runs])
        lengths = np.array([r.end - r.start for r in section.runs])
        unique = np.unique(coords)
        if len(unique) < max(3, scale * 0.35):
            continue
        slope, intercept = np.polyfit(coords, centers, 1)
        if abs(slope) > 0.18 or float(
            np.max(np.abs(centers - (slope * coords + intercept)))
        ) > max(1.5, scale * 0.08):
            continue
        lo, hi = float(coords.min()), float(coords.max() + 1)
        fragments.append(
            [
                lo,
                hi,
                float(slope),
                float(intercept),
                float(np.median(lengths)),
                float(len(unique)),
            ]
        )
    fragments.sort(key=lambda f: f[0])
    merged = []
    for fragment in fragments:
        best = None
        for prior in merged:
            gap = fragment[0] - prior[1]
            midpoint = (fragment[0] + prior[1]) / 2
            distance = abs((fragment[2] - prior[2]) * midpoint + fragment[3] - prior[3])
            if (
                -1 <= gap <= max(2, scale * 0.45)
                and distance <= max(1.5, min(fragment[4], prior[4]))
                and abs(fragment[2] - prior[2]) <= 0.08
            ):
                if best is None or gap < fragment[0] - best[1]:
                    best = prior
        if best is None:
            merged.append(fragment)
        else:
            weight = best[5] + fragment[5]
            for k in (2, 3, 4):
                best[k] = (best[k] * best[5] + fragment[k] * fragment[5]) / weight
            best[1] = max(best[1], fragment[1])
            best[5] = weight
    result = []
    for lo, hi, slope, intercept, thick, count in merged:
        length = hi - lo
        if length < scale * (0.65 if orientation == "horizontal" else 0.9):
            continue
        support = min(1.0, count / length)
        if support < 0.65:
            continue
        if orientation == "horizontal" and length > scale * 1.8:
            # A digit crossing terminates a thin-run section. Continue the fitted
            # stroke through that crossing only while real black ink supports it.
            for direction in (-1, 1):
                edge = int(lo) - 1 if direction < 0 else int(hi)
                for step in range(int(scale * 0.9)):
                    x = edge + direction * step
                    if x < 0 or x >= binary.shape[1]:
                        break
                    y = slope * x + intercept
                    top = max(0, math.floor(y - thick / 2))
                    bottom = min(binary.shape[0], math.ceil(y + thick / 2))
                    if bottom <= top or np.mean(binary[top:bottom, x] == 0) < 0.6:
                        break
                    if direction < 0:
                        lo = float(x)
                    else:
                        hi = float(x + 1)
        first = (lo, slope * lo + intercept)
        last = (hi, slope * hi + intercept)
        if orientation == "vertical":
            first = first[::-1]
            last = last[::-1]
        xs, ys = zip(first, last)
        pad = thick / 2
        box = Box(
            min(xs) - (pad if orientation == "vertical" else 0),
            min(ys) - (pad if orientation == "horizontal" else 0),
            abs(last[0] - first[0]) + (thick if orientation == "vertical" else 0),
            abs(last[1] - first[1]) + (thick if orientation == "horizontal" else 0),
        )
        result.append(Filament(orientation, (first, last), thick, support, box))
    return tuple(result)


def erase_filaments(
    binary: np.ndarray, lines: tuple[Filament, ...], min_length: float
) -> np.ndarray:
    clean = binary.copy()
    for line in lines:
        a, b = line.points
        if math.dist(a, b) < min_length:
            continue
        steps = max(1, int(math.dist(a, b)))
        # Erase only the fitted stroke, never its full enclosing rectangle.
        for ratio in np.linspace(0, 1, steps + 1):
            x = a[0] + ratio * (b[0] - a[0])
            y = a[1] + ratio * (b[1] - a[1])
            half = line.thickness / 2
            if line.orientation == "horizontal":
                left, right = int(x), int(x) + 1
                top, bottom = math.floor(y - half), math.ceil(y + half)
            else:
                left, right = math.floor(x - half), math.ceil(x + half)
                top, bottom = int(y), int(y) + 1
            clean[
                max(0, top) : min(clean.shape[0], bottom),
                max(0, left) : min(clean.shape[1], right),
            ] = 255
    return clean
