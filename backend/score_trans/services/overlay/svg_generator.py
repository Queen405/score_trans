from __future__ import annotations

import base64
from functools import cache

from PIL import ImageFont

from ...models.common.paths import PROJECT_ROOT
from .omr_parser import InterData, SheetModel


_BRAVURA_PATH = (
    PROJECT_ROOT / "third_party" / "audiveris" / "app" / "res" / "Bravura.otf"
)
_FONT_METRIC_SIZE = 1000

_CATEGORY_COLORS: dict[str, str] = {
    "note": "#00aa44",
    "frame": "#0066ff",
    "modifier": "#cc00cc",
    "physical": "#00aa44",
    "lyrics": "#0088cc",
    "other": "#aa8800",
}

_TAG_CATEGORY: dict[str, str] = {
    "head": "note",
    "rest": "note",
    "augmentation-dot": "note",
    "beam": "note",
    "beam-hook": "note",
    "flag": "note",
    "clef": "frame",
    "barline": "frame",
    "time-whole": "frame",
    "time-custom": "frame",
    "alter": "modifier",
    "key": "modifier",
    "bow": "modifier",
    "articulation": "modifier",
    "tuplet": "modifier",
    "stem": "physical",
    "ledger": "physical",
    "slur": "physical",
    "sentence": "physical",
    "word": "physical",
    "lyric-item": "lyrics",
}

_GEOMETRIC_TAGS: frozenset[str] = frozenset(
    {
        "stem",
        "beam",
        "beam-hook",
        "slur",
        "barline",
        "ledger",
    }
)

_SMUFL_CODEPOINTS: dict[str, int] = {
    "ACCENT": 0xE4A0,
    "AUGMENTATION_DOT": 0xE044,
    "BOW_DOWN": 0xE610,
    "BOW_UP": 0xE612,
    "BREVE_REST": 0xE4E2,
    "C_CLEF": 0xE05C,
    "COMMON_TIME": 0xE08A,
    "CUT_TIME": 0xE08B,
    "DOUBLE_FLAT": 0xE264,
    "DOUBLE_SHARP": 0xE263,
    "EIGHTH_REST": 0xE4E6,
    "FERMATA": 0xE4C0,
    "FERMATA_BELOW": 0xE4C1,
    "FLAG_1": 0xE240,
    "FLAG_1_DOWN": 0xE241,
    "FLAG_2": 0xE242,
    "FLAG_2_DOWN": 0xE243,
    "FLAG_3": 0xE244,
    "FLAG_3_DOWN": 0xE245,
    "FLAG_4": 0xE246,
    "FLAG_4_DOWN": 0xE247,
    "FLAG_5": 0xE248,
    "FLAG_5_DOWN": 0xE249,
    "FLAT": 0xE260,
    "F_CLEF": 0xE062,
    "F_CLEF_8VA": 0xE065,
    "F_CLEF_8VB": 0xE064,
    "F_CLEF_SMALL": 0xE07C,
    "G_CLEF": 0xE050,
    "G_CLEF_8VA": 0xE053,
    "G_CLEF_8VB": 0xE052,
    "G_CLEF_SMALL": 0xE07A,
    "HALF_REST": 0xE4E4,
    "KEY_CANCEL": 0xE261,
    "LONG_REST": 0xE4E1,
    "MARCATO": 0xE4AC,
    "MARCATO_BELOW": 0xE4AD,
    "NATURAL": 0xE261,
    "NOTEHEAD_BLACK": 0xE0A4,
    "NOTEHEAD_CIRCLE_X": 0xE0B3,
    "NOTEHEAD_CIRCLE_X_VOID": 0xE0B2,
    "NOTEHEAD_CROSS": 0xE0A9,
    "NOTEHEAD_CROSS_VOID": 0xE0A8,
    "NOTEHEAD_DIAMOND_FILLED": 0xE0DB,
    "NOTEHEAD_DIAMOND_VOID": 0xE0D9,
    "NOTEHEAD_TRIANGLE_DOWN_FILLED": 0xE0C7,
    "NOTEHEAD_TRIANGLE_DOWN_VOID": 0xE0C5,
    "NOTEHEAD_VOID": 0xE0A3,
    "ONE_16TH_REST": 0xE4E7,
    "ONE_32ND_REST": 0xE4E8,
    "ONE_64TH_REST": 0xE4E9,
    "ONE_128TH_REST": 0xE4EA,
    "PERCUSSION_CLEF": 0xE069,
    "QUARTER_REST": 0xE4E5,
    "SHARP": 0xE262,
    "STACCATISSIMO": 0xE4A6,
    "STACCATISSIMO_BELOW": 0xE4A7,
    "STACCATO": 0xE4A2,
    "TENUTO": 0xE4A4,
    "TIME_EIGHT": 0xE088,
    "TIME_FIVE": 0xE085,
    "TIME_FOUR": 0xE084,
    "TIME_NINE": 0xE089,
    "TIME_ONE": 0xE081,
    "TIME_SEVEN": 0xE087,
    "TIME_SIX": 0xE086,
    "TIME_THREE": 0xE083,
    "TIME_TWO": 0xE082,
    "TIME_ZERO": 0xE080,
    "TUPLET_SIX": 0xE886,
    "TUPLET_THREE": 0xE883,
    "WHOLE_REST": 0xE4E3,
}


class SvgGenerator:
    """Render a :class:`SheetModel` into a transparent SVG overlay string."""

    def generate(self, sheet: SheetModel) -> str:
        parts: list[str] = []
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {sheet.width} {sheet.height}" '
            f'width="{sheet.width}" height="{sheet.height}">'
        )
        parts.append("<style>")
        if _has_renderable_symbols(sheet) and (font_data := _font_data()) is not None:
            parts.append(
                "  @font-face { font-family: BravuraOverlay; "
                f"src: url(data:font/otf;base64,{font_data}) format('opentype'); }}"
            )
        for category, color in _CATEGORY_COLORS.items():
            parts.append(f"  .cat-{category} {{ fill: {color}; stroke: {color}; }}")
        parts.append("  rect.bounds { fill-opacity: 0.12; stroke-width: 1; }")
        parts.append("  .geo { fill-opacity: 1; }")
        parts.append(
            "  .symbol { font-family: BravuraOverlay; font-style: normal; "
            "font-weight: normal; stroke: none; }"
        )
        parts.append("</style>")
        parts.append('<g class="overlay">')
        for inter in sheet.inters:
            category = _TAG_CATEGORY.get(inter.tag, "other")
            color = _CATEGORY_COLORS[category]
            opacity = _clamp(inter.grade, 0.0, 1.0)
            geo = _geometric_svg(inter, color, opacity)
            if geo:
                parts.append(f"  {geo}")
                continue
            symbol = _symbol_svg(inter, category, color, opacity)
            if symbol:
                parts.append(f"  {symbol}")
                continue
            parts.append(
                f'  <rect class="bounds cat-{category}" '
                f'x="{inter.bounds[0]}" y="{inter.bounds[1]}" '
                f'width="{inter.bounds[2]}" height="{inter.bounds[3]}" '
                f'opacity="{opacity:.2f}"/>'
            )
        parts.append("</g>")
        parts.append("</svg>")
        return "\n".join(parts)


def _has_renderable_symbols(sheet: SheetModel) -> bool:
    return any(inter.shape in _SMUFL_CODEPOINTS for inter in sheet.inters)


@cache
def _font_data() -> str | None:
    try:
        return base64.b64encode(_BRAVURA_PATH.read_bytes()).decode("ascii")
    except OSError:
        return None


@cache
def _font() -> ImageFont.FreeTypeFont | None:
    try:
        return ImageFont.truetype(str(_BRAVURA_PATH), _FONT_METRIC_SIZE)
    except OSError:
        return None


@cache
def _glyph_bounds(codepoint: int) -> tuple[int, int, int, int] | None:
    font = _font()
    if font is None:
        return None
    return font.getbbox(chr(codepoint), anchor="ls")


def _symbol_svg(
    inter: InterData,
    category: str,
    color: str,
    opacity: float,
) -> str | None:
    codepoint = _SMUFL_CODEPOINTS.get(inter.shape)
    if codepoint is None or _font_data() is None:
        return None
    glyph_bounds = _glyph_bounds(codepoint)
    if glyph_bounds is None:
        return None

    gx1, gy1, gx2, gy2 = glyph_bounds
    glyph_width = gx2 - gx1
    glyph_height = gy2 - gy1
    if glyph_width <= 0 or glyph_height <= 0:
        return None

    x, y, width, height = inter.bounds
    scale = min(width / glyph_width, height / glyph_height)
    rendered_width = glyph_width * scale
    rendered_height = glyph_height * scale
    left = x + ((width - rendered_width) / 2)
    top = y + ((height - rendered_height) / 2)
    baseline_x = left - (gx1 * scale)
    baseline_y = top - (gy1 * scale)
    font_size = _FONT_METRIC_SIZE * scale
    return (
        f'<text class="symbol cat-{category}" data-shape="{inter.shape}" '
        f'x="{baseline_x:.2f}" y="{baseline_y:.2f}" '
        f'font-size="{font_size:.2f}" fill="{color}" '
        f'opacity="{opacity:.2f}">&#x{codepoint:X};</text>'
    )


def _geometric_svg(inter: InterData, color: str, opacity: float) -> str | None:
    tag = inter.tag
    if tag not in _GEOMETRIC_TAGS:
        return None

    if tag == "stem" and inter.median is not None:
        sw = inter.width if inter.width and inter.width > 0 else 3.0
        return _line(inter.median, sw, color, opacity)

    if tag in ("beam", "beam-hook") and inter.median is not None:
        h = inter.height if inter.height and inter.height > 0 else 6.0
        return _parallelogram(inter.median, h, color, opacity)

    if tag == "slur" and inter.curve is not None:
        return _bezier_path(inter.curve, color, opacity)

    if tag == "barline" and inter.median is not None:
        sw = inter.width if inter.width and inter.width > 0 else 2.0
        return _line(inter.median, sw, color, opacity)

    if tag == "ledger" and inter.median is not None:
        sw = inter.thickness if inter.thickness and inter.thickness > 0 else 3.0
        return _line(inter.median, sw, color, opacity)

    return None


def _line(
    median: tuple[float, float, float, float],
    stroke_width: float,
    color: str,
    opacity: float,
) -> str:
    x1, y1, x2, y2 = median
    return (
        f'<line class="geo" x1="{x1:.1f}" y1="{y1:.1f}" '
        f'x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{stroke_width:.1f}" '
        f'stroke-linecap="butt" opacity="{opacity:.2f}"/>'
    )


def _parallelogram(
    median: tuple[float, float, float, float],
    height: float,
    color: str,
    opacity: float,
) -> str:
    x1, y1, x2, y2 = median
    if abs(x2 - x1) < 0.01 and abs(y2 - y1) < 0.01:
        return ""
    h2 = height / 2.0
    pts = [
        (x1, y1 - h2),
        (x2, y2 - h2),
        (x2, y2 + h2),
        (x1, y1 + h2),
    ]
    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (
        f'<polygon class="geo" points="{points_str}" '
        f'fill="{color}" opacity="{opacity:.2f}"/>'
    )


def _bezier_path(
    curve: tuple[float, float, float, float, float, float, float, float],
    color: str,
    opacity: float,
) -> str:
    x1, y1, cx1, cy1, cx2, cy2, x2, y2 = curve
    d = (
        f"M {x1:.1f},{y1:.1f} "
        f"C {cx1:.1f},{cy1:.1f} {cx2:.1f},{cy2:.1f} {x2:.1f},{y2:.1f}"
    )
    return (
        f'<path class="geo" d="{d}" fill="none" '
        f'stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" opacity="{opacity:.2f}"/>'
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
