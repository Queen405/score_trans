from __future__ import annotations

import numpy as np
from ..models.raster import Filament, RowGeometry


def barline_candidates(
    binary: np.ndarray, band: RowGeometry, candidates: tuple[Filament, ...]
) -> tuple[Filament, ...]:
    """Projection inside a local notation band, verified along the fitted stroke."""
    height = band.digit_height
    accepted = []
    for line in candidates:
        a, b = line.points
        x = (a[0] + b[0]) / 2
        top = band.top.y_at(x)
        bottom = band.bottom.y_at(x)
        if (
            line.bounds.y > top + height * 0.25
            or line.bounds.bottom < bottom - height * 0.15
        ):
            continue
        ys = np.arange(max(0, int(top)), min(binary.shape[0], int(bottom) + 1))
        if len(ys) == 0:
            continue
        xs = a[0] + (ys - a[1]) * (b[0] - a[0]) / max(b[1] - a[1], 1)
        radius = max(1, int(np.ceil(line.thickness / 2)))
        occupied = sum(
            np.any(
                binary[
                    y,
                    max(0, int(x) - radius) : min(binary.shape[1], int(x) + radius + 1),
                ]
                == 0
            )
            for y, x in zip(ys, xs, strict=True)
        )
        if occupied / len(ys) >= 0.72:
            accepted.append(line)
    return tuple(accepted)
