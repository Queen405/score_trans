from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from fractions import Fraction

import pytest
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path
from score_trans.domain.performance_marks import PERFORMANCE_MARKS, PerformanceMark
from score_trans.models.score import Event, JianpuPitch, JianpuScore, Measure
from score_trans.services.render.engraving.scene import BBox
from score_trans.services.render.main import render_score_svg


TEXT_RENDERERS = {
    "trill",
    "fingering",
    "open-string",
    "inner-string",
    "outer-string",
}
PRIMITIVE_TAGS = {"path", "line", "circle", "ellipse"}


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _local_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _mark_group(root: ET.Element, mark_id: str) -> ET.Element:
    return next(
        node
        for node in root.iter()
        if "performance-mark" in node.attrib.get("class", "").split()
        and node.attrib.get("data-mark") == mark_id
    )


def _render_mark(mark: PerformanceMark) -> ET.Element:
    pitch = JianpuPitch(3)
    pitches = [pitch, JianpuPitch(5)] if mark.target == "chord" else [pitch]
    event = Event(kind="note", duration=Fraction(1), pitches=pitches)
    if mark.category == "articulation":
        event.articulations = [mark.id]
        event.articulation = mark.id
    elif mark.category == "ornament":
        event.ornaments = [mark.id]
    else:
        event.technical = [mark.id]
    score = JianpuScore(measures=[Measure("1", duration=Fraction(4), events=[event])])
    return _root(render_score_svg(score))


def _bbox(node: ET.Element) -> BBox:
    x, y, width, height = (float(value) for value in node.attrib["data-bbox"].split())
    return BBox(x, y, width, height)


def _path_bbox(node: ET.Element) -> BBox:
    pen = BoundsPen(None)
    parse_path(node.attrib["d"], pen)
    assert pen.bounds is not None
    left, top, right, bottom = pen.bounds
    stroke = float(node.attrib.get("stroke-width", "0")) / 2
    return BBox(
        left - stroke,
        top - stroke,
        right - left + stroke * 2,
        bottom - top + stroke * 2,
    )


def _primitive_bbox(node: ET.Element) -> BBox:
    tag = _local_name(node)
    stroke = float(node.attrib.get("stroke-width", "0")) / 2
    if tag == "path":
        return _path_bbox(node)
    if tag == "line":
        x1 = float(node.attrib["x1"])
        x2 = float(node.attrib["x2"])
        y1 = float(node.attrib["y1"])
        y2 = float(node.attrib["y2"])
        return BBox(
            min(x1, x2) - stroke,
            min(y1, y2) - stroke,
            abs(x2 - x1) + stroke * 2,
            abs(y2 - y1) + stroke * 2,
        )
    if tag == "circle":
        cx = float(node.attrib["cx"])
        cy = float(node.attrib["cy"])
        radius = float(node.attrib["r"])
        return BBox(
            cx - radius - stroke,
            cy - radius - stroke,
            (radius + stroke) * 2,
            (radius + stroke) * 2,
        )
    if tag == "ellipse":
        cx = float(node.attrib["cx"])
        cy = float(node.attrib["cy"])
        rx = float(node.attrib["rx"])
        ry = float(node.attrib["ry"])
        return BBox(
            cx - rx - stroke,
            cy - ry - stroke,
            (rx + stroke) * 2,
            (ry + stroke) * 2,
        )
    raise AssertionError(f"unsupported performance-mark primitive: {tag}")


def _transformed_primitive_bbox(group: ET.Element, node: ET.Element) -> BBox:
    local = _primitive_bbox(node)
    match = re.fullmatch(
        r"translate\(([-\d.]+) ([-\d.]+)\) scale\(([-\d.]+)\)",
        group.attrib["transform"],
    )
    assert match is not None
    x, y, scale = (float(value) for value in match.groups())
    return BBox(
        x + local.x * scale,
        y + local.y * scale,
        local.width * scale,
        local.height * scale,
    )


def _contains(outer: BBox, inner: BBox, tolerance: float = 0.01) -> bool:
    return (
        outer.x <= inner.x + tolerance
        and outer.y <= inner.y + tolerance
        and outer.x + outer.width + tolerance >= inner.x + inner.width
        and outer.y + outer.height + tolerance >= inner.y + inner.height
    )


def test_tremolo_renders_three_vector_slashes_instead_of_tofu() -> None:
    root = _root(
        render_score_svg(
            JianpuScore(
                measures=[
                    Measure(
                        "1",
                        events=[
                            Event(
                                kind="note",
                                duration=Fraction(1),
                                pitches=[JianpuPitch(3)],
                                ornaments=["tremolo"],
                            )
                        ],
                    )
                ]
            )
        )
    )

    group = _mark_group(root, "tremolo")
    paths = [node for node in group.iter() if _local_name(node) == "path"]

    assert len(paths) == 1
    assert len(re.findall(r"\bM\b", paths[0].attrib["d"])) == 3
    assert not any((node.text or "") in {"≋", "□"} for node in group.iter())


def test_arpeggio_renders_a_tall_vector_wave_instead_of_tofu() -> None:
    mark = next(mark for mark in PERFORMANCE_MARKS if mark.id == "arpeggio")
    group = _mark_group(_render_mark(mark), mark.id)
    path = next(node for node in group.iter() if _local_name(node) == "path")
    box = _path_bbox(path)

    assert box.height > box.width * 2
    assert not any((node.text or "") in {"∿", "□"} for node in group.iter())


@pytest.mark.parametrize(
    "mark",
    [mark for mark in PERFORMANCE_MARKS if mark.category != "spanner"],
    ids=lambda mark: mark.id,
)
def test_registered_marks_render_through_the_graphics_contract(
    mark: PerformanceMark,
) -> None:
    group = _mark_group(_render_mark(mark), mark.id)
    classes = group.attrib["class"].split()

    assert mark.category in classes
    assert group.attrib["aria-label"] == mark.id
    assert _bbox(group).width > 0
    assert _bbox(group).height > 0
    assert not any(
        (node.text or "") == mark.id
        for node in group.iter()
        if mark.renderer not in TEXT_RENDERERS
    )


@pytest.mark.parametrize(
    "mark",
    [
        mark
        for mark in PERFORMANCE_MARKS
        if mark.category != "spanner" and mark.renderer not in TEXT_RENDERERS
    ],
    ids=lambda mark: mark.id,
)
def test_vector_mark_bbox_contains_every_rendered_primitive(
    mark: PerformanceMark,
) -> None:
    group = _mark_group(_render_mark(mark), mark.id)
    group_box = _bbox(group)
    primitives = [
        node
        for node in group.iter()
        if _local_name(node) in PRIMITIVE_TAGS
        and "performance-mark-primitive" in node.attrib.get("class", "").split()
    ]

    assert primitives
    assert all(
        _contains(group_box, _transformed_primitive_bbox(group, node))
        for node in primitives
    )


def test_vector_mark_primitives_have_explicit_export_paint() -> None:
    mark = next(mark for mark in PERFORMANCE_MARKS if mark.id == "string-sweep")
    group = _mark_group(_render_mark(mark), mark.id)
    primitives = [
        node
        for node in group.iter()
        if "performance-mark-primitive" in node.attrib.get("class", "").split()
    ]

    assert primitives
    for primitive in primitives:
        classes = primitive.attrib["class"].split()
        if "performance-mark-stroke" in classes:
            assert primitive.attrib["stroke"] == "#171717"
            assert float(primitive.attrib["stroke-width"]) > 0
            assert primitive.attrib["fill"] == "none"
        if "performance-mark-fill" in classes:
            assert primitive.attrib["fill"] == "#171717"


def test_performance_mark_group_carries_exact_source_semantics() -> None:
    event = Event(
        kind="note",
        duration=Fraction(1),
        pitches=[JianpuPitch(3, source_id="note-3")],
        technical=["guzheng-vibrato"],
        source_ids=["note-3", "vibrato-3"],
        source_roles={"note": ["note-3"], "technical": ["vibrato-3"]},
    )
    score = JianpuScore(measures=[Measure("1", events=[event])])

    group = _mark_group(_root(render_score_svg(score)), "guzheng-vibrato")

    assert group.attrib["data-source-role"] == "technical"
    assert group.attrib["data-source-ids"] == "vibrato-3"
