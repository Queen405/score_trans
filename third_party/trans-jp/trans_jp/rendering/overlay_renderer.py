from __future__ import annotations
from xml.sax.saxutils import escape
from ..models.contracts import RowResult, make_source_id
from .primitive_renderer import render_primitive

ROLE_COLORS = {
    "note": "#00aa44",
    "rest": "#888888",
    "barline": "#0066ff",
    "chord": "#00aa44",
    "slur": "#0088cc",
    "tie": "#0088cc",
    "other": "#888888",
}


def generate_overlay_svg(
    rows: list[RowResult],
    image_width: int,
    image_height: int,
    glyphs: dict,
    *,
    debug: bool = False,
) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{image_width}" height="{image_height}" viewBox="0 0 {image_width} {image_height}">'
    ]
    if debug:
        for result in rows:
            if result.analysis is None:
                continue
            for orientation, lines, color in (
                ("horizontal", result.analysis.horizontal, "#d946ef"),
                ("vertical", result.analysis.vertical, "#f97316"),
            ):
                for line in lines:
                    a, b = [
                        result.row.transform.point(x, y + result.row.work_y_top)
                        for x, y in line.points
                    ]
                    parts.append(
                        f'<path data-candidate="{orientation}" d="M{a[0]:.4f},{a[1]:.4f} L{b[0]:.4f},{b[1]:.4f}" stroke="{color}" stroke-width="0.7" fill="none" opacity="0.6"/>'
                    )
    drawn = set()
    for result in rows:
        for token in result.tokens:
            geometry = token.geometry
            source_id = make_source_id(result.row.index, token.index)
            if geometry is None or not geometry.primitives:
                continue
            color = ROLE_COLORS.get(token.role, ROLE_COLORS["other"])
            parts.append(
                f'<g id="{source_id}" data-source-id="{source_id}" data-status="{geometry.status}">'
            )
            for primitive in geometry.primitives:
                key = (
                    primitive.kind,
                    primitive.bounds,
                    primitive.value,
                    primitive.points,
                    primitive.thickness,
                    color,
                )
                if key not in drawn:
                    parts.append(render_primitive(primitive, color, glyphs))
                    drawn.add(key)
            if debug and geometry.bounds:
                b = geometry.bounds
                parts.append(
                    f'<rect x="{b.x:.5f}" y="{b.y:.5f}" width="{b.width:.5f}" height="{b.height:.5f}" fill="none" stroke="#ff8800" stroke-width="0.7"/>'
                )
                parts.append(f"<title>{escape(token.text)}</title>")
            parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)
