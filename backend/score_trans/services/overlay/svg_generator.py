from __future__ import annotations

import math
from xml.sax.saxutils import escape

from .omr_parser import InterData, SheetModel


_CATEGORY_COLORS: dict[str, str] = {
    "note": "#008844",
    "clef": "#0066cc",
    "stem": "#806040",
    "slur": "#4444aa",
    "bar": "#333333",
    "acc": "#992299",
    "time": "#0066cc",
    "other": "#888888",
}

_TAG_CATEGORY: dict[str, str] = {
    "head": "note",
    "rest": "note",
    "augmentation-dot": "note",
    "clef": "clef",
    "stem": "stem",
    "beam": "stem",
    "beam-hook": "stem",
    "flag": "stem",
    "slur": "slur",
    "barline": "bar",
    "alter": "acc",
    "key": "acc",
    "time-whole": "time",
    "time-custom": "time",
}

_GEOMETRIC_TAGS: frozenset[str] = frozenset({
    "stem",
    "beam",
    "beam-hook",
    "slur",
    "barline",
    "ledger",
})


class SvgGenerator:
    """Render a :class:`SheetModel` into a transparent SVG overlay string."""

    def generate(self, sheet: SheetModel) -> str:
        parts: list[str] = []
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {sheet.width} {sheet.height}" '
            f'width="{sheet.width}" height="{sheet.height}">'
        )
        parts.append("<style>")
        for category, color in _CATEGORY_COLORS.items():
            parts.append(
                f"  .cat-{category} {{ fill: {color}; stroke: {color}; }}"
            )
        parts.append("  rect.bounds { fill-opacity: 0.12; stroke-width: 1; }")
        parts.append("  .geo { fill-opacity: 1; }")
        parts.append("</style>")
        parts.append('<g class="overlay">')
        for inter in sheet.inters:
            category = _TAG_CATEGORY.get(inter.tag, "other")
            color = _CATEGORY_COLORS[category]
            opacity = _clamp(inter.grade, 0.0, 1.0)
            parts.append(
                f'  <rect class="bounds cat-{category}" '
                f'x="{inter.bounds[0]}" y="{inter.bounds[1]}" '
                f'width="{inter.bounds[2]}" height="{inter.bounds[3]}" '
                f'opacity="{opacity:.2f}"/>'
            )
            geo = _geometric_svg(inter, color, opacity)
            if geo:
                parts.append(f"  {geo}")
        parts.append("</g>")
        parts.append("</svg>")
        return "\n".join(parts)


def _geometric_svg(inter: InterData, color: str, opacity: float) -> str | None:
    tag = inter.tag
    if tag not in _GEOMETRIC_TAGS:
        return None

    if tag == "stem" and inter.median is not None:
        sw = inter.width if inter.width and inter.width > 0 else 3.0
        return _line(inter.median, sw, color, opacity)

    if tag in ("beam", "beam-hook") and inter.median is not None:
        h = inter.height if inter.height and inter.height > 0 else 6.0
        return _parallelogram(inter.median, h, color, opacity)

    if tag == "slur" and inter.curve is not None:
        return _bezier_path(inter.curve, color, opacity)

    if tag == "barline" and inter.median is not None:
        sw = inter.width if inter.width and inter.width > 0 else 2.0
        return _line(inter.median, sw, color, opacity)

    if tag == "ledger" and inter.median is not None:
        sw = inter.width if inter.width and inter.width > 0 else 2.0
        return _line(inter.median, sw, color, opacity)

    return None


def _line(
    median: tuple[float, float, float, float],
    stroke_width: float,
    color: str,
    opacity: float,
) -> str:
    x1, y1, x2, y2 = median
    return (
        f'<line class="geo" x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{stroke_width:.1f}" '
        f'stroke-linecap="butt" opacity="{opacity:.2f}"/>'
    )


def _parallelogram(
    median: tuple[float, float, float, float],
    height: float,
    color: str,
    opacity: float,
) -> str:
    x1, y1, x2, y2 = median
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.01:
        return ""
    nx = -dy / length
    ny = dx / length
    h2 = height / 2.0
    pts = [
        (x1 + nx * h2, y1 + ny * h2),
        (x2 + nx * h2, y2 + ny * h2),
        (x2 - nx * h2, y2 - ny * h2),
        (x1 - nx * h2, y1 - ny * h2),
    ]
    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (
        f'<polygon class="geo" points="{points_str}" '
        f'fill="{color}" opacity="{opacity:.2f}"/>'
    )


def _bezier_path(
    curve: tuple[float, float, float, float, float, float, float, float],
    color: str,
    opacity: float,
) -> str:
    x1, y1, cx1, cy1, cx2, cy2, x2, y2 = curve
    d = (
        f"M {x1:.1f},{y1:.1f} "
        f"C {cx1:.1f},{cy1:.1f} {cx2:.1f},{cy2:.1f} {x2:.1f},{y2:.1f}"
    )
    return (
        f'<path class="geo" d="{d}" fill="none" '
        f'stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" opacity="{opacity:.2f}"/>'
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
