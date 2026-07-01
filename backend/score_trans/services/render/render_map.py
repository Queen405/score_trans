from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET


def write_render_map(svg_path: Path, page_index: int) -> Path | None:
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError):
        return None
    source_boxes: dict[str, dict[str, float] | None] = {}
    for element in root.iter():
        for source_id in (element.get("data-source-ids") or "").split():
            if source_id:
                bbox = _parse_bbox(element.get("data-bbox"))
                source_boxes[source_id] = _merge_bbox(source_boxes.get(source_id), bbox)
    if not source_boxes:
        return None
    payload = {
        "version": 1,
        "page_index": page_index,
        "anchors": [
            _render_anchor(source_id, page_index, source_boxes[source_id])
            for source_id in sorted(source_boxes)
        ],
    }
    path = svg_path.with_suffix(".render-map.json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _render_anchor(
    source_id: str, page_index: int, bbox: dict[str, float] | None
) -> dict[str, object]:
    anchor: dict[str, object] = {
        "source_id": source_id,
        "page_index": page_index,
        "selector": f'g[data-source-ids~="{source_id}"]',
    }
    if bbox is not None:
        anchor["bbox"] = bbox
    return anchor


def _parse_bbox(value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    try:
        x, y, width, height = (float(part) for part in value.split())
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return {"x": x, "y": y, "width": width, "height": height}


def _merge_bbox(
    current: dict[str, float] | None, incoming: dict[str, float] | None
) -> dict[str, float] | None:
    if current is None:
        return incoming
    if incoming is None:
        return current
    x1 = min(current["x"], incoming["x"])
    y1 = min(current["y"], incoming["y"])
    x2 = max(current["x"] + current["width"], incoming["x"] + incoming["width"])
    y2 = max(current["y"] + current["height"], incoming["y"] + incoming["height"])
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
