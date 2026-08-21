from __future__ import annotations

from typing import TypedDict

from .scene import BBox, PublicationScene, SceneNode
from .style import PublicationStyle


class GeometryIssue(TypedDict):
    kind: str
    classes: tuple[str, ...]
    bbox: tuple[float, float, float, float]


def check_scene_geometry(
    scene: PublicationScene, style: PublicationStyle
) -> list[GeometryIssue]:
    """Return deterministic diagnostics for rendered event geometry.

    The checker intentionally considers only source-anchor groups for overlap
    reporting.  Page chrome, nested primitive nodes, and spanners are not
    treated as peer events and therefore cannot create false positives.
    """

    issues: list[GeometryIssue] = []
    anchors: list[tuple[tuple[str, ...], BBox]] = []
    for node in scene.nodes:
        classes = tuple(node.attrs.get("class", "").split())
        if "page-background" in classes:
            continue
        bbox = _node_bbox(node)
        if bbox is None:
            continue
        if (
            bbox.x < style.margin_left
            or bbox.y < 0
            or bbox.x + bbox.width > scene.width - style.margin_right
            or bbox.y + bbox.height > scene.height
        ):
            issues.append(
                {
                    "kind": "page-overflow",
                    "classes": classes,
                    "bbox": (bbox.x, bbox.y, bbox.width, bbox.height),
                }
            )
        if "source-anchor" in classes:
            anchors.append((classes, bbox))

    for index, (left_classes, left_box) in enumerate(anchors):
        for right_classes, right_box in anchors[index + 1 :]:
            if _overlaps(left_box, right_box):
                issues.append(
                    {
                        "kind": "event-overlap",
                        "classes": tuple(sorted(set(left_classes + right_classes))),
                        "bbox": _union(left_box, right_box),
                    }
                )
    return issues


def _node_bbox(node: SceneNode) -> BBox | None:
    raw = node.attrs.get("data-bbox")
    if raw is not None:
        values = [float(value) for value in str(raw).split()]
        if len(values) == 4:
            return BBox(*values)
    if node.tag == "circle":
        cx = float(node.attrs.get("cx", 0))
        cy = float(node.attrs.get("cy", 0))
        radius = float(node.attrs.get("r", 0))
        return BBox(cx - radius, cy - radius, radius * 2, radius * 2)
    if node.tag == "line":
        x1 = float(node.attrs.get("x1", 0))
        x2 = float(node.attrs.get("x2", 0))
        y1 = float(node.attrs.get("y1", 0))
        y2 = float(node.attrs.get("y2", 0))
        stroke = float(node.attrs.get("stroke-width", 0)) / 2
        return BBox(
            min(x1, x2) - stroke,
            min(y1, y2) - stroke,
            abs(x2 - x1) + stroke * 2,
            abs(y2 - y1) + stroke * 2,
        )
    return None


def _overlaps(left: BBox, right: BBox) -> bool:
    return (
        left.x < right.x + right.width
        and right.x < left.x + left.width
        and left.y < right.y + right.height
        and right.y < left.y + left.height
    )


def _union(left: BBox, right: BBox) -> tuple[float, float, float, float]:
    x1 = min(left.x, right.x)
    y1 = min(left.y, right.y)
    x2 = max(left.x + left.width, right.x + right.width)
    y2 = max(left.y + left.height, right.y + right.height)
    return (x1, y1, x2 - x1, y2 - y1)
