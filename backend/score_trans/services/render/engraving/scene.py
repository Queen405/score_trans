from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Mapping


def _fmt(value: float | int | str) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


@dataclass(frozen=True, slots=True)
class BBox:
    x: float
    y: float
    width: float
    height: float

    def as_data(self) -> str:
        return " ".join(_fmt(v) for v in (self.x, self.y, self.width, self.height))

    def scaled(self, factor: float) -> "BBox":
        return BBox(
            self.x * factor,
            self.y * factor,
            self.width * factor,
            self.height * factor,
        )


@dataclass(frozen=True, slots=True)
class GeometryRecord:
    owner: str
    kind: str
    bbox: BBox
    classes: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()
    allow_overlap: bool = False


@dataclass(slots=True)
class SceneNode:
    tag: str
    attrs: dict[str, str | float | int] = field(default_factory=dict)
    text: str | None = None
    children: list["SceneNode"] = field(default_factory=list)

    def to_svg(self, indent: int = 0) -> str:
        pad = "  " * indent
        attrs = "".join(
            f' {name}="{escape(_fmt(value), quote=True)}"'
            for name, value in self.attrs.items()
            if value is not None
        )
        if not self.children and self.text is None:
            return f"{pad}<{self.tag}{attrs} />"
        body: list[str] = []
        if self.text is not None:
            body.append(escape(self.text))
        body.extend(child.to_svg(indent + 1) for child in self.children)
        if self.children:
            return (
                f"{pad}<{self.tag}{attrs}>\n"
                + "\n".join(body)
                + f"\n{pad}</{self.tag}>"
            )
        return f"{pad}<{self.tag}{attrs}>{''.join(body)}</{self.tag}>"


@dataclass(slots=True)
class PublicationScene:
    width: float
    height: float
    page_index: int
    coordinate_scale: float = 1.0
    layout_key: str = ""
    nodes: list[SceneNode] = field(default_factory=list)
    source_boxes: dict[str, BBox] = field(default_factory=dict)
    geometry_records: list[GeometryRecord] = field(default_factory=list)
    geometry_issues: list[dict[str, object]] = field(default_factory=list)
    note_index_start: int | None = None
    note_index_end: int | None = None
    playback_start_tick: int | None = None
    playback_end_tick: int | None = None
    playback_ppq: int = 480

    def add(self, node: SceneNode) -> SceneNode:
        self.nodes.append(node)
        return node

    def register_sources(self, source_ids: list[str], bbox: BBox) -> None:
        for source_id in source_ids:
            current = self.source_boxes.get(source_id)
            self.source_boxes[source_id] = (
                bbox if current is None else _union(current, bbox)
            )

    def render_map_payload(self) -> Mapping[str, object]:
        return {
            "version": 1,
            "page_index": self.page_index,
            "anchors": [
                {
                    "source_id": source_id,
                    "page_index": self.page_index,
                    "selector": f'g[data-source-ids~="{source_id}"]',
                    "bbox": {
                        "x": bbox.x,
                        "y": bbox.y,
                        "width": bbox.width,
                        "height": bbox.height,
                    },
                }
                for source_id, raw_bbox in sorted(self.source_boxes.items())
                for bbox in [raw_bbox.scaled(self.coordinate_scale)]
            ],
            "diagnostics": [
                _scaled_geometry_issue(issue, self.coordinate_scale)
                for issue in self.geometry_issues
            ],
        }


def _union(left: BBox, right: BBox) -> BBox:
    x1 = min(left.x, right.x)
    y1 = min(left.y, right.y)
    x2 = max(left.x + left.width, right.x + right.width)
    y2 = max(left.y + left.height, right.y + right.height)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def _scaled_geometry_issue(
    issue: dict[str, object], factor: float
) -> dict[str, object]:
    scaled = dict(issue)
    bbox = issue.get("bbox")
    if isinstance(bbox, tuple) and len(bbox) == 4:
        scaled["bbox"] = tuple(float(value) * factor for value in bbox)
    return scaled
