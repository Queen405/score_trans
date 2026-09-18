from __future__ import annotations
from xml.sax.saxutils import escape
from ..models.geometry import Primitive


def render_primitive(p: Primitive, color: str, glyphs: dict) -> str:
    b = p.bounds
    if p.kind == "glyph":
        glyph = glyphs[p.value]
        x0, y0, x1, y1 = glyph["bounds"]
        if len(p.points) == 3:
            origin, right, bottom = p.points
            a = (right[0] - origin[0]) / (x1 - x0)
            bxy = (right[1] - origin[1]) / (x1 - x0)
            c = (bottom[0] - origin[0]) / (y0 - y1)
            d = (bottom[1] - origin[1]) / (y0 - y1)
            e = origin[0] - a * x0 - c * y1
            f = origin[1] - bxy * x0 - d * y1
            transform = f"matrix({a:.9f} {bxy:.9f} {c:.9f} {d:.9f} {e:.9f} {f:.9f})"
        else:
            transform = (
                f"translate({p.bounds.x:.5f} {p.bounds.y:.5f}) "
                f"scale({p.bounds.width / (x1 - x0):.9f} {-p.bounds.height / (y1 - y0):.9f}) "
                f"translate({-x0:g} {-y1:g})"
            )
        return (
            f'<path data-symbol="{escape(p.value)}" d="{glyph["path"]}" fill="{color}" '
            f'transform="{transform}"/>'
        )
    if p.kind == "dot":
        return f'<ellipse data-mark="{p.value}" cx="{b.cx:.5f}" cy="{b.cy:.5f}" rx="{b.width / 2:.5f}" ry="{b.height / 2:.5f}" fill="{color}"/>'
    if p.kind == "curve":
        thickness = min(p.thickness, max(0.5, b.height * 0.4))
        y = b.bottom - thickness / 2
        control = y - (b.height - thickness) * 4 / 3
        d = f"M{b.x + thickness / 2:.5f},{y:.5f} C{b.x + b.width / 3:.5f},{control:.5f} {b.x + b.width * 2 / 3:.5f},{control:.5f} {b.right - thickness / 2:.5f},{y:.5f}"
    else:
        thickness = p.thickness
        a, z = p.points
        d = f"M{a[0]:.5f},{a[1]:.5f} L{z[0]:.5f},{z[1]:.5f}"
    return f'<path data-mark="{p.value}" d="{d}" stroke="{color}" stroke-width="{thickness:.5f}" fill="none"/>'
