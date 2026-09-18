from __future__ import annotations

import numpy as np
from ..models.raster import Run, Orientation


def scan_runs(
    binary: np.ndarray, orientation: Orientation = "horizontal"
) -> tuple[Run, ...]:
    pixels = binary if orientation == "horizontal" else binary.T
    runs = []
    for coordinate, row in enumerate(pixels):
        changes = np.diff(np.r_[False, row == 0, False].astype(np.int8))
        runs.extend(
            Run(coordinate, int(a), int(b))
            for a, b in zip(
                np.flatnonzero(changes == 1), np.flatnonzero(changes == -1), strict=True
            )
        )
    return tuple(runs)
