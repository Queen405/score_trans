"""Bounding-box coercion utilities."""

from __future__ import annotations

from typing import Any


def coerce_bbox(raw: Any) -> tuple[float, float, float, float] | None:
    """Coerce various bbox formats into (x1, y1, x2, y2)."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        nested = _first_present(
            raw,
            ("bbox", "bbox_2d", "box", "bounding_box", "boundingBox", "coordinates", "points"),
        )
        if nested is not None and nested is not raw:
            return coerce_bbox(nested)
        if all(key in raw for key in ("x1", "y1", "x2", "y2")):
            return (float(raw["x1"]), float(raw["y1"]), float(raw["x2"]), float(raw["y2"]))
        if all(key in raw for key in ("left", "top", "right", "bottom")):
            return (
                float(raw["left"]),
                float(raw["top"]),
                float(raw["right"]),
                float(raw["bottom"]),
            )
        if all(key in raw for key in ("x", "y", "width", "height")):
            x = float(raw["x"])
            y = float(raw["y"])
            return (x, y, x + float(raw["width"]), y + float(raw["height"]))
        if all(key in raw for key in ("x", "y", "w", "h")):
            x = float(raw["x"])
            y = float(raw["y"])
            return (x, y, x + float(raw["w"]), y + float(raw["h"]))
        return None
    if isinstance(raw, (list, tuple)) and len(raw) == 4 and all(
        isinstance(value, (int, float, str)) for value in raw
    ):
        return tuple(float(value) for value in raw)
    return coerce_bbox_points(raw)


def coerce_bbox_points(raw: Any) -> tuple[float, float, float, float] | None:
    """Coerce a list of points into a bbox."""
    if not isinstance(raw, (list, tuple)):
        return None

    if len(raw) == 8 and all(isinstance(value, (int, float, str)) for value in raw):
        xs = [float(value) for value in raw[0::2]]
        ys = [float(value) for value in raw[1::2]]
        return (min(xs), min(ys), max(xs), max(ys))

    points: list[tuple[float, float]] = []
    for point in raw:
        if isinstance(point, dict) and "x" in point and "y" in point:
            points.append((float(point["x"]), float(point["y"])))
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            points.append((float(point[0]), float(point[1])))

    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return (min(xs), min(ys), max(xs), max(ys))

    return None


def _first_present(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None
