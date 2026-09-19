from __future__ import annotations

import numpy as np
from ..models.geometry import Box, Transform
from ..models.lyrics import TextRegion
from ..raster.filaments import detect_filaments, erase_filaments
from .lyric_regions import intervals


def split_mixed_region(
    binary: np.ndarray,
    region: TextRegion,
    transform: Transform,
    band_boxes: tuple[Box, ...] = (),
) -> tuple[list[TextRegion], list[dict]]:
    """Break only long connecting rules in a temporary analysis mask."""
    b = region.bounds_work
    x, y, w, h = map(int, (b.x, b.y, b.width, b.height))
    crop = binary[y : y + h, x : x + w]
    scale = max(8, h * 0.2)
    horizontal = tuple(
        line
        for line in detect_filaments(crop, "horizontal", scale)
        if line.bounds.width > max(6 * scale, w * 0.55)
    )
    vertical = tuple(
        line
        for line in detect_filaments(crop, "vertical", scale)
        if line.bounds.height > max(1.5 * scale, h * 0.5)
    )
    mask = erase_filaments(crop, horizontal + vertical, 0)
    children = []
    projection = (mask == 0).sum(axis=1)
    threshold = max(2, float(projection.max()) * 0.08)
    for top, bottom in intervals(
        projection >= threshold, max(1, round(transform.scale_y))
    ):
        if bottom - top < max(4, 3 * transform.scale_y):
            continue
        for left, right in intervals(
            (mask[top:bottom] == 0).any(axis=0),
            max(5, round((bottom - top) * (0.65 if h < 80 else 2))),
        ):
            # Bounds are tightened against original pixels, not fabricated from text.
            ys, xs = np.nonzero(crop[top:bottom, left:right] == 0)
            if len(xs) < 8:
                continue
            box = Box(
                x + left + int(xs.min()),
                y + top + int(ys.min()),
                int(xs.max() - xs.min() + 1),
                int(ys.max() - ys.min() + 1),
            )
            children.append(
                TextRegion(
                    f"{region.region_id}:sub{len(children):03d}",
                    box,
                    transform.box(box),
                )
            )
    erased = [
        {
            "orientation": line.orientation,
            "points": list(line.points),
            "thickness": line.thickness,
        }
        for line in horizontal + vertical
    ]
    # No subdivision is preferable to inventing ownership for the same full crop.
    if not 1 < len(children) <= 24:
        children = [
            TextRegion(f"{region.region_id}:sub{i:03d}", box, transform.box(box))
            for i, box in enumerate(band_boxes)
        ]
        if not 1 < len(children) <= 24:
            return [], erased
    return children, erased
