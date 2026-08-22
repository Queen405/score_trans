from __future__ import annotations

from typing import TypedDict

from .scene import BBox, GeometryRecord, PublicationScene, SceneNode
from .style import PublicationStyle


class GeometryIssue(TypedDict):
    kind: str
    classes: tuple[str, ...]
    bbox: tuple[float, float, float, float]
    owner: str | None


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
    records: list[GeometryRecord] = []
    for node, _parent_classes, parent_owner in _walk_nodes(scene.nodes):
        classes = tuple(node.attrs.get("class", "").split())
        if "page-background" in classes:
            continue
        bbox = _node_bbox(node)
        if bbox is None:
            continue
        source_ids = tuple(str(node.attrs.get("data-source-ids", "")).split())
        owner = (
            str(node.attrs.get("data-geometry-owner", ""))
            or " ".join(source_ids)
            or parent_owner
            or ":".join(classes)
            or "scene"
        )
        kind = str(
            node.attrs.get("data-span-kind", "")
            or (classes[0] if classes else node.tag)
        )
        records.append(GeometryRecord(owner, kind, bbox, classes, source_ids))
        if (
            bbox.x < 0
            or bbox.y < 0
            or bbox.x + bbox.width > scene.width
            or bbox.y + bbox.height > scene.height
        ):
            issues.append(
                {
                    "kind": "page-overflow",
                    "classes": classes,
                    "bbox": (bbox.x, bbox.y, bbox.width, bbox.height),
                    "owner": owner,
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
                        "owner": None,
                    }
                )
    for index, left_record in enumerate(records):
        for right_record in records[index + 1 :]:
            if left_record.kind in {"source-anchor", "g"} and right_record.kind in {
                "source-anchor",
                "g",
            }:
                continue
            if left_record.owner == right_record.owner:
                continue
            if _overlaps(left_record.bbox, right_record.bbox):
                issues.append(
                    {
                        "kind": "geometry-overlap",
                        "classes": tuple(
                            sorted(set(left_record.classes + right_record.classes))
                        ),
                        "bbox": _union(left_record.bbox, right_record.bbox),
                        "owner": f"{left_record.owner}|{right_record.owner}",
                    }
                )
    scene.geometry_records = records
    scene.geometry_issues = issues
    return issues


def _walk_nodes(
    nodes: list[SceneNode],
    parent_classes: tuple[str, ...] = (),
    parent_owner: str | None = None,
):
    for node in nodes:
        classes = tuple(node.attrs.get("class", "").split())
        source_ids = tuple(str(node.attrs.get("data-source-ids", "")).split())
        owner = " ".join(source_ids) or parent_owner or ":".join(classes) or "scene"
        yield node, parent_classes, owner
        yield from _walk_nodes(node.children, classes or parent_classes, owner)


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
