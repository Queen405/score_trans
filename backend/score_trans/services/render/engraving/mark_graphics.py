from __future__ import annotations

from dataclasses import dataclass

from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path

from ....domain.performance_marks import get_performance_mark
from ....models.common.errors import RenderError
from .fonts import font_registry
from .scene import BBox, SceneNode
from .style import PublicationStyle


_BASE_SIZE = 15.0
_TEXT_RENDERERS = frozenset(
    {
        "trill",
        "fingering",
        "open-string",
        "inner-string",
        "outer-string",
        "fallback-text",
    }
)


@dataclass(frozen=True, slots=True)
class _GraphicSpec:
    renderer: str
    box: BBox


def _text_label(mark_id: str, renderer: str) -> str:
    if renderer == "fallback-text":
        return mark_id
    if renderer == "trill":
        return "tr"
    if renderer == "fingering":
        return mark_id.rsplit("-", 1)[-1]
    return {
        "open-string": "0",
        "inner-string": "内",
        "outer-string": "外",
    }.get(renderer, mark_id)


def _spec(mark_id: str) -> _GraphicSpec:
    mark = get_performance_mark(mark_id)
    if mark is None:
        label = _text_label(mark_id, "fallback-text")
        left, top, right, bottom = font_registry().ink_bounds(label, _BASE_SIZE)
        return _GraphicSpec(
            "fallback-text",
            BBox(
                left - font_registry().measure(label, _BASE_SIZE) / 2,
                top,
                right - left,
                bottom - top,
            ),
        )
    if mark.renderer == "directional-slide":
        raise RenderError(f"连续滑音不能作为普通演奏标记绘制：{mark_id}")
    renderer = mark.renderer
    if renderer in _TEXT_RENDERERS:
        label = _text_label(mark_id, renderer)
        left, top, right, bottom = font_registry().ink_bounds(label, _BASE_SIZE)
        advance = font_registry().measure(label, _BASE_SIZE)
        return _GraphicSpec(
            renderer,
            BBox(left - advance / 2, top, right - left, bottom - top),
        )
    if renderer == "staccato":
        radius = 2.4
        return _GraphicSpec(renderer, BBox(-radius, -radius, radius, radius))
    return _GraphicSpec(renderer, BBox(0, 0, mark.visual_width, mark.visual_height))


def mark_graphic_box(mark_id: str, style: PublicationStyle) -> BBox:
    """Return the mark ink box in the event coordinate system."""

    spec = _spec(mark_id)
    factor = style.annotation_size / _BASE_SIZE
    if spec.renderer in _TEXT_RENDERERS:
        return BBox(
            spec.box.x * factor,
            spec.box.y * factor,
            spec.box.width * factor,
            spec.box.height * factor,
        )
    mark = get_performance_mark(mark_id)
    assert mark is not None
    primitives = _primitive_nodes(spec.renderer, mark_id, "technical", style)
    actual = _primitive_bounds(primitives)
    if spec.renderer == "staccato":
        return BBox(
            actual.x * factor,
            actual.y * factor,
            actual.width * factor,
            actual.height * factor,
        )
    width = max(actual.width, mark.visual_width)
    height = max(actual.height, mark.visual_height)
    centered = BBox(
        actual.x + (actual.width - width) / 2,
        actual.y + (actual.height - height) / 2,
        width,
        height,
    )
    return BBox(
        centered.x * factor,
        centered.y * factor,
        centered.width * factor,
        centered.height * factor,
    )


def build_mark_graphic(
    mark_id: str,
    x: float,
    y: float,
    style: PublicationStyle,
    *,
    role: str,
    source_attrs: dict[str, str | float | int],
) -> SceneNode:
    """Build one deterministic, semantically-addressable performance mark."""

    spec = _spec(mark_id)
    factor = style.annotation_size / _BASE_SIZE
    local_box = mark_graphic_box(mark_id, style)
    bbox = BBox(x + local_box.x, y + local_box.y, local_box.width, local_box.height)
    classes = f"performance-mark {role}"
    if spec.renderer == "staccato":
        classes += " staccato"
    attrs: dict[str, str | float | int] = {
        "class": classes,
        "data-mark": mark_id,
        "aria-label": mark_id,
        "data-bbox": bbox.as_data(),
        "transform": f"translate({x:g} {y:g}) scale({factor:g})",
        **source_attrs,
    }
    group = SceneNode("g", attrs)
    group.children.extend(_primitive_nodes(spec.renderer, mark_id, role, style))
    return group


def _path(
    d: str,
    *,
    fill: str = "none",
    stroke: str = "#171717",
    stroke_width: float = 1.7,
    role: str,
) -> SceneNode:
    classes = f"performance-mark-primitive {role}"
    if fill == "none":
        classes += " performance-mark-stroke technique-mark"
    else:
        classes += " performance-mark-fill"
    return SceneNode(
        "path",
        {
            "class": classes,
            "d": d,
            "stroke": stroke,
            "stroke-width": stroke_width,
            "fill": fill,
        },
    )


def _line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    role: str,
    width: float = 1.7,
) -> SceneNode:
    return SceneNode(
        "line",
        {
            "class": f"performance-mark-primitive {role} performance-mark-stroke technique-mark",
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "stroke": "#171717",
            "stroke-width": width,
            "fill": "none",
        },
    )


def _circle(
    cx: float,
    cy: float,
    radius: float,
    *,
    role: str,
    fill: str = "none",
    width: float = 1.7,
) -> SceneNode:
    classes = f"performance-mark-primitive {role}"
    if fill == "none":
        classes += " performance-mark-stroke technique-mark"
    else:
        classes += " performance-mark-fill"
    return SceneNode(
        "circle",
        {
            "class": classes,
            "cx": cx,
            "cy": cy,
            "r": radius,
            "stroke": "#171717",
            "stroke-width": width,
            "fill": fill,
        },
    )


def _ellipse(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    *,
    role: str,
) -> SceneNode:
    return SceneNode(
        "ellipse",
        {
            "class": f"performance-mark-primitive {role} performance-mark-stroke technique-mark",
            "cx": cx,
            "cy": cy,
            "rx": rx,
            "ry": ry,
            "stroke": "#171717",
            "stroke-width": 1.7,
            "fill": "none",
        },
    )


def _text(value: str, *, role: str) -> SceneNode:
    return SceneNode(
        "text",
        {
            "class": f"performance-mark-primitive {role}",
            "x": 0,
            "y": 4,
            "font-size": _BASE_SIZE,
            "text-anchor": "middle",
        },
        value,
    )


def _primitive_bounds(nodes: list[SceneNode]) -> BBox:
    bounds: BBox | None = None
    for node in nodes:
        tag = node.tag
        stroke = float(node.attrs.get("stroke-width", 0)) / 2
        if tag == "path":
            pen = BoundsPen(None)
            parse_path(str(node.attrs["d"]), pen)
            if pen.bounds is None:
                continue
            left, top, right, bottom = pen.bounds
            current = BBox(
                left - stroke,
                top - stroke,
                right - left + stroke * 2,
                bottom - top + stroke * 2,
            )
        elif tag == "line":
            x1 = float(node.attrs["x1"])
            y1 = float(node.attrs["y1"])
            x2 = float(node.attrs["x2"])
            y2 = float(node.attrs["y2"])
            current = BBox(
                min(x1, x2) - stroke,
                min(y1, y2) - stroke,
                abs(x2 - x1) + stroke * 2,
                abs(y2 - y1) + stroke * 2,
            )
        elif tag == "circle":
            cx = float(node.attrs["cx"])
            cy = float(node.attrs["cy"])
            radius = float(node.attrs["r"]) + stroke
            current = BBox(cx - radius, cy - radius, radius * 2, radius * 2)
        elif tag == "ellipse":
            cx = float(node.attrs["cx"])
            cy = float(node.attrs["cy"])
            rx = float(node.attrs["rx"]) + stroke
            ry = float(node.attrs["ry"]) + stroke
            current = BBox(cx - rx, cy - ry, rx * 2, ry * 2)
        else:
            continue
        bounds = current if bounds is None else _union(bounds, current)
    if bounds is None:
        raise RenderError("演奏标记没有可见图元")
    return bounds


def _union(left: BBox, right: BBox) -> BBox:
    x = min(left.x, right.x)
    y = min(left.y, right.y)
    right_edge = max(left.x + left.width, right.x + right.width)
    bottom_edge = max(left.y + left.height, right.y + right.height)
    return BBox(x, y, right_edge - x, bottom_edge - y)


def _primitive_nodes(
    renderer: str,
    mark_id: str,
    role: str,
    style: PublicationStyle,
) -> list[SceneNode]:
    width = style.stroke_width
    if renderer in _TEXT_RENDERERS:
        return [_text(_text_label(mark_id, renderer), role=role)]
    if renderer == "staccato":
        radius = 2.4
        return [
            _path(
                f"M {-radius:g} {-radius:g} L {radius:g} {-radius:g} L 0 {radius:g} Z",
                fill="#171717",
                stroke="none",
                stroke_width=0,
                role=role,
            )
        ]
    if renderer == "accent":
        return [_path("M -8 -5 L 8 0 L -8 5", role=role, stroke_width=width)]
    if renderer == "tenuto":
        return [_line(-7, 0, 7, 0, role=role, width=width)]
    if renderer == "fermata":
        return [
            _path("M -10 4 Q 0 -9, 10 4", role=role, stroke_width=width),
            _circle(0, 2, 2.2, role=role, fill="#171717", width=0),
        ]
    if renderer == "three-slash":
        return [
            _path(
                "M 0 0 L 10 -4 M 0 5 L 10 1 M 0 10 L 10 6",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "down-bow":
        return [_path("M -7 6 V -5 H 7 V 6", role=role, stroke_width=width)]
    if renderer == "up-bow":
        return [_path("M -7 -5 L 0 6 L 7 -5", role=role, stroke_width=width)]
    if renderer == "throw-bow":
        return [
            _path(
                "M -6 -5 Q 1 -7, 2 0 Q 3 7, -4 6 M 2 1 L 7 -3",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "natural-harmonic":
        return [_circle(0, 0, 4.5, role=role, width=width)]
    if renderer == "artificial-harmonic":
        return [_path("M 0 -6 L 5 0 L 0 6 L -5 0 Z", role=role, stroke_width=width)]
    if renderer == "pluck":
        return [_path("M -5 0 H 5 M 0 -5 V 5", role=role, stroke_width=width)]
    if renderer == "scoop":
        return [
            _path(
                "M -7 6 Q -1 6, 6 -6 M 1 -5 L 6 -6 L 5 -1",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "plop":
        return [
            _path(
                "M -7 -6 Q -1 -6, 6 6 M 1 5 L 6 6 L 5 1", role=role, stroke_width=width
            )
        ]
    if renderer == "finger-pad-slide":
        return [
            _path(
                "M -6 5 Q -1 -6, 4 3 M -2 6 Q 3 -5, 8 2", role=role, stroke_width=width
            )
        ]
    if renderer in {"doit", "falloff"}:
        end_y = -10 if renderer == "doit" else 10
        start_y = 4 if renderer == "doit" else -4
        return [
            _path(f"M -7 {start_y} Q 0 0, 10 {end_y}", role=role, stroke_width=width)
        ]
    if renderer in {"lower-return-slide", "upper-return-slide"}:
        direction = 1 if renderer == "lower-return-slide" else -1
        return [
            _path(
                f"M -7 0 Q 2 {direction * 10}, 8 {direction * 3} Q 4 {direction}, 1 0",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer in {"upper-trill", "lower-trill"}:
        notch = " M 0 2 L 0 8" if renderer == "lower-trill" else ""
        return [
            _path(
                f"M -9 0 q 3 -4, 6 0 q 3 4, 6 0 q 3 -4, 6 0{notch}",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "breath-mark":
        return [
            _path(
                "M -2 -3 Q 4 -2, 1 7 Q -1 4, 1 0 Z",
                fill="#171717",
                stroke="none",
                stroke_width=0,
                role=role,
            )
        ]
    if renderer == "hook-string":
        return [_path("M -3 -7 V 4 Q -2 8, 5 4", role=role, stroke_width=width)]
    if renderer == "guzheng-sweep-tremolo":
        return [
            _path(
                "M -11 -4 q 3 -5 6 0 h 3 q 3 5 6 0 M -11 5 q 3 -5 6 0 h 3 q 3 5 6 0 M -7 -8 v 4 M 7 1 v 4",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "string-sweep":
        return [
            _path(
                "M -8 10 L 8 -10 M 2 -9 L 8 -10 L 7 -4 M -7 4 L -1 9 M -3 -1 L 3 4 M 1 -6 L 7 -1",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "guzheng-double-tuo":
        return [
            _path(
                "M -10 6 V -4 H -3 Q 0 -4, 0 -1 V 2 M -1 6 V -4 H 6 Q 9 -4, 9 -1 V 2",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "guzheng-double-mo":
        return [_path("M -7 -6 L 2 5 M -1 -7 L 8 4", role=role, stroke_width=width)]
    if renderer == "arpeggio":
        return [
            _path(
                "M 0 -15 q -5 3 0 6 q 5 3 0 6 q -5 3 0 6 q 5 3 0 6 q -5 3 0 6",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "ornament-note":
        return [
            _ellipse(-2, 4, 3.8, 2.8, role=role),
            _path("M 1 3 V -9 Q 8 -6, 5 -1", role=role, stroke_width=width),
        ]
    if renderer == "guzheng-board-front-flower":
        return [
            _path(
                "M 0 -10 V 2 M -6 -7 L 6 -1 M 6 -7 L -6 -1 M -7 5 H 7 M -5 9 H 5",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "guzheng-on-beat-flower":
        return [
            _path(
                "M 0 -9 V 9 M -9 0 H 9 M -6.5 -6.5 L 6.5 6.5 M 6.5 -6.5 L -6.5 6.5",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer in {"guzheng-ascending-scrape", "guzheng-descending-scrape"}:
        direction = -1 if renderer == "guzheng-ascending-scrape" else 1
        end_y = direction * 10
        start_y = -direction * 8
        return [
            _path(
                f"M -9 {start_y} L 9 {end_y} M 3 {end_y - direction} L 9 {end_y} L 8 {end_y - direction * 6}",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer == "guzheng-vibrato":
        return [
            _path(
                "M -11 0 q 3 -4 6 0 q 3 4 6 0 q 3 -4 6 0 q 3 4 6 0",
                role=role,
                stroke_width=width,
            )
        ]
    if renderer in {"guzheng-ornament-up-slide", "guzheng-ornament-down-slide"}:
        direction = -1 if renderer == "guzheng-ornament-up-slide" else 1
        return [
            _path(
                f"M -7 {-direction * 6} H -1 V {direction} Q 4 {direction * 8}, 8 {direction * 2} M -6 {-direction * 2} H -2",
                role=role,
                stroke_width=width,
            )
        ]
    raise RenderError(f"演奏标记缺少图形实现：{mark_id} ({renderer})")
