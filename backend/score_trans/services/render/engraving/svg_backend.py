from __future__ import annotations

import re
from html import escape

from ....models.render.layout import PUBLICATION_ENGINE_VERSION
from .fonts import font_registry
from .scene import PublicationScene, SceneNode
from .style import PublicationStyle

_CSS = """
.page-background{fill:#fff}.score-title{font-weight:600;letter-spacing:.08em}
.score-meta,.measure-attribute,.part-name,.measure-no,.annotation,.lyric{fill:#181818}
.note,.accidental,.score-title,.score-meta,.part-name,.measure-no,.annotation,.lyric,.tuplet-number,.dynamic,.technique{font-family:ScoreTransNotoSerif,serif}
.music-symbol{font-family:ScoreTransBravura,serif}.note{font-weight:600}
.measure,.system-bracket,.duration-line,.beam-line,.extension-line,.ending-line,.repeat-dot,.staff-line{stroke:#171717;fill:none;stroke-linecap:round}
.tie,.slur,.slide{stroke:#171717;stroke-width:1.8;fill:none;stroke-linecap:round}
.performance-mark-stroke{stroke:#171717;fill:none;stroke-linecap:round;stroke-linejoin:round}
.performance-mark-fill{fill:#171717;stroke:none}
.tuplet-bracket{stroke:#171717;stroke-width:1.4;fill:none}.octave-dot,.rhythm-dot{fill:#171717}
.playback-current .note{fill:#1677ff}.source-highlight{filter:drop-shadow(0 0 3px #ff9f1a)}
""".strip()

_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_SIMPLE_CLASS_SELECTOR_RE = re.compile(r"\.([A-Za-z0-9_-]+)")

# MuPDF 不解析 <style> 块，导出 PDF/PNG 时这些绘制属性必须内联到元素上；
# font-family/font-weight 等排版属性对字形路径无意义（且引擎不引用系统字体），不内联。
_INLINE_PROPERTIES = frozenset(
    {
        "fill",
        "fill-opacity",
        "fill-rule",
        "opacity",
        "stroke",
        "stroke-dasharray",
        "stroke-dashoffset",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-opacity",
        "stroke-width",
    }
)


def _parse_css_rules(css: str) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    for selectors, body in _CSS_RULE_RE.findall(css):
        properties: dict[str, str] = {}
        for declaration in body.split(";"):
            name, separator, value = declaration.partition(":")
            name = name.strip()
            if separator and name in _INLINE_PROPERTIES:
                properties[name] = value.strip()
        if not properties:
            continue
        for selector in selectors.split(","):
            match = _SIMPLE_CLASS_SELECTOR_RE.fullmatch(selector.strip())
            if match:
                rules.setdefault(match.group(1), {}).update(properties)
    return rules


_CLASS_STYLES = _parse_css_rules(_CSS)


def _inline_class_styles(
    attrs: dict[str, str | float | int],
) -> dict[str, str | float | int]:
    classes = str(attrs.get("class") or "").split()
    if not classes:
        return attrs
    merged = dict(attrs)
    for class_name in classes:
        for name, value in _CLASS_STYLES.get(class_name, {}).items():
            merged.setdefault(name, value)
    return merged


def scene_to_svg(scene: PublicationScene, style: PublicationStyle) -> str:
    scale = scene.coordinate_scale
    body = "\n".join(_node_to_svg(node, 2, scale) for node in scene.nodes)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width:g}" '
        f'height="{scene.height:g}" viewBox="0 0 {scene.width:g} {scene.height:g}" '
        f'data-render-engine="publication" data-engine-version="{PUBLICATION_ENGINE_VERSION}" '
        f'data-layout-key="{escape(scene.layout_key, quote=True)}">\n'
        f"  <style>{_CSS}</style>\n"
        f'  <g class="publication-content" transform="scale({scale:g})">\n'
        f"{body}\n  </g>\n</svg>"
    )


def _node_to_svg(node: SceneNode, indent: int, metadata_scale: float) -> str:
    if node.tag != "text" or node.text is None:
        if not node.children:
            attrs = _scaled_metadata_attrs(node.attrs, metadata_scale)
            return SceneNode(node.tag, _inline_class_styles(attrs)).to_svg(indent)
        pad = "  " * indent
        attrs = _attrs(
            _inline_class_styles(_scaled_metadata_attrs(node.attrs, metadata_scale))
        )
        children = "\n".join(
            _node_to_svg(child, indent + 1, metadata_scale) for child in node.children
        )
        return f"{pad}<{node.tag}{attrs}>\n{children}\n{pad}</{node.tag}>"
    pad = "  " * indent
    x = float(node.attrs.get("x", 0))
    y = float(node.attrs.get("y", 0))
    size = float(node.attrs.get("font-size", 16))
    anchor = str(node.attrs.get("text-anchor", "start"))
    glyphs, advance = font_registry().paths(node.text)
    offset = (
        -advance / 2 if anchor == "middle" else (-advance if anchor == "end" else 0.0)
    )
    group_attrs = {
        key: value
        for key, value in node.attrs.items()
        if key not in {"x", "y", "font-size", "text-anchor"}
    }
    group_attrs["aria-label"] = node.text
    group_attrs["data-font-size"] = size * metadata_scale
    group_attrs["transform"] = (
        f"translate({x:g} {y:g}) scale({size:g} {-size:g}) translate({offset:g} 0)"
    )
    group_attrs = _inline_class_styles(
        _scaled_metadata_attrs(group_attrs, metadata_scale)
    )
    paths = []
    for glyph in glyphs:
        paths.append(
            f'{pad}  <path d="{escape(glyph.path, quote=True)}" '
            f'transform="translate({glyph.cursor_em:g} 0) scale({1 / glyph.units_per_em:g})" />'
        )
    hidden = (
        f'{pad}  <text x="0" y="0" opacity="0" aria-hidden="true">'
        f"{escape(node.text)}</text>"
    )
    return (
        f"{pad}<g{_attrs(group_attrs)}>\n"
        + "\n".join([*paths, hidden])
        + f"\n{pad}</g>"
    )


def _scaled_metadata_attrs(
    attrs: dict[str, str | float | int], factor: float
) -> dict[str, str | float | int]:
    if factor == 1.0:
        return attrs
    scaled = dict(attrs)
    raw_bbox = scaled.get("data-bbox")
    if raw_bbox is not None:
        try:
            values = [float(value) * factor for value in str(raw_bbox).split()]
        except ValueError:
            values = []
        if len(values) == 4:
            scaled["data-bbox"] = " ".join(_value(value) for value in values)
    return scaled


def _attrs(attrs: dict[str, str | float | int]) -> str:
    return "".join(
        f' {name}="{escape(_value(value), quote=True)}"'
        for name, value in attrs.items()
        if value is not None
    )


def _value(value: str | float | int) -> str:
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)
