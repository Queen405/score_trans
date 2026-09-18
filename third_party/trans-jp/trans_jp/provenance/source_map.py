from __future__ import annotations
from ..models.contracts import RowResult, make_source_id
from ..models.geometry import Box


def rect_path(box: Box) -> str:
    return f"M{box.x:.1f},{box.y:.1f} L{box.right:.1f},{box.y:.1f} L{box.right:.1f},{box.bottom:.1f} L{box.x:.1f},{box.bottom:.1f} Z"


def build_source_map(
    rows: list[RowResult],
    image_width: int,
    image_height: int,
    overlay_filename: str = "overlay.svg",
) -> dict:
    elements = []
    for row in rows:
        for token in row.tokens:
            geometry = token.geometry
            if geometry is None or geometry.bounds is None:
                continue
            bounds = geometry.bounds.clip(image_width, image_height)
            if bounds.width <= 0 or bounds.height <= 0:
                continue
            boxes = [
                (p.hit_bounds or p.bounds).clip(image_width, image_height)
                for p in geometry.primitives
            ]
            elements.append(
                {
                    "source_id": make_source_id(row.row.index, token.index),
                    "inter_id": token.index,
                    "shape": token.role.upper(),
                    "grade": row.confidence if row.confidence is not None else 0.5,
                    "bounds": {
                        "x": bounds.x,
                        "y": bounds.y,
                        "width": bounds.width,
                        "height": bounds.height,
                    },
                    "hit_path": " ".join(
                        rect_path(b) for b in boxes if b.width > 0 and b.height > 0
                    ),
                    "musicxml_locator": {"attribute": "id", "contains": ""},
                }
            )
    return {
        "version": 1,
        "sheets": [
            {
                "sheet_index": 0,
                "width": image_width,
                "height": image_height,
                "overlay_file": overlay_filename,
                "elements": elements,
            }
        ],
    }
