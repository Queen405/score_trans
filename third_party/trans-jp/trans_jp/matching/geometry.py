from __future__ import annotations
from ..models.contracts import RowSegment
from ..models.geometry import Box, Primitive, TokenGeometry
from ..models.raster import Filament


def page_box(row: RowSegment, box: Box) -> Box:
    return row.transform.box(Box(box.x, box.y + row.work_y_top, box.width, box.height))


def add_shape(
    row: RowSegment, geometry: TokenGeometry, kind: str, box: Box, value: str = ""
) -> None:
    corners = (
        tuple(
            row.transform.point(x, y + row.work_y_top)
            for x, y in ((box.x, box.y), (box.right, box.y), (box.x, box.bottom))
        )
        if kind == "glyph"
        else ()
    )
    geometry.primitives.append(Primitive(kind, page_box(row, box), value, corners))


def add_line(
    row: RowSegment,
    geometry: TokenGeometry,
    line: Filament,
    value: str = "",
    hit: Box | None = None,
) -> None:
    points = tuple(row.transform.point(x, y + row.work_y_top) for x, y in line.points)
    scale = (
        row.transform.scale_y
        if line.orientation == "horizontal"
        else row.transform.scale_x
    )
    geometry.primitives.append(
        Primitive(
            "line",
            page_box(row, line.bounds),
            value,
            points,
            line.thickness / scale,
            page_box(row, hit) if hit else None,
        )
    )
