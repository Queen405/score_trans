from __future__ import annotations

from html import escape

from .fonts import font_registry
from .scene import SceneNode
from .scene import PublicationScene
from .style import PublicationStyle


_CSS = """
.page-background{fill:#fff}.score-title{font-weight:600;letter-spacing:.08em}
.score-meta,.measure-attribute,.part-name,.measure-no,.annotation,.lyric{fill:#181818}
.note,.accidental,.score-title,.score-meta,.part-name,.measure-no,.annotation,.lyric,.tuplet-number,.dynamic,.technique{font-family:ScoreTransNotoSerif,serif}
.music-symbol{font-family:ScoreTransBravura,serif}.note{font-weight:600}
.measure,.system-bracket,.duration-line,.beam-line,.extension-line,.ending-line,.repeat-dot,.staff-line{stroke:#171717;fill:none;stroke-linecap:round}
.tie,.slur,.slide{stroke:#171717;stroke-width:1.8;fill:none;stroke-linecap:round}
.tuplet-bracket{stroke:#171717;stroke-width:1.4;fill:none}.octave-dot,.rhythm-dot{fill:#171717}
.playback-current .note{fill:#1677ff}.source-highlight{filter:drop-shadow(0 0 3px #ff9f1a)}
""".strip()


def scene_to_svg(scene: PublicationScene, style: PublicationStyle) -> str:
    body = "\n".join(_node_to_svg(node, 1) for node in scene.nodes)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width:g}" '
        f'height="{scene.height:g}" viewBox="0 0 {scene.width:g} {scene.height:g}" '
        f'data-render-engine="publication" data-engine-version="publication-4">\n'
        f"  <style>{_CSS}</style>\n{body}\n</svg>"
    )


def _node_to_svg(node: SceneNode, indent: int) -> str:
    if node.tag != "text" or node.text is None:
        if not node.children:
            return node.to_svg(indent)
        pad = "  " * indent
        attrs = _attrs(node.attrs)
        children = "\n".join(_node_to_svg(child, indent + 1) for child in node.children)
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
    group_attrs["data-font-size"] = size
    group_attrs["transform"] = (
        f"translate({x:g} {y:g}) scale({size:g} {-size:g}) translate({offset:g} 0)"
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
