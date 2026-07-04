from __future__ import annotations

from ..options import RenderOptions
from ..utils.text import _esc


def _px(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _svg_styles(options: RenderOptions, *, standalone_page: bool) -> list[str]:
    styles = [
        f"text {{ font-family: {options.font_family}; fill: #171717; letter-spacing: 0; }}",
    ]
    if not standalone_page:
        styles.extend(
            [
                ".title { font-size: 40px; font-weight: 700; }",
                ".meta { font-size: 23px; }",
            ]
        )
    styles.extend(
        [
            f".note {{ font-size: {_px(options.note_font_size)}px; font-weight: 650; }}",
            f".accidental {{ font-size: {_px(options.accidental_font_size)}px; font-weight: 400; }}",
            ".bar { stroke: #252525; stroke-width: 1.6; stroke-linecap: square; }",
        ]
    )
    if not standalone_page:
        styles.extend(
            [
                ".beat-guide { stroke: #e2dacd; stroke-width: 0.8; stroke-dasharray: 2 10; }",
                ".staff-line { stroke: #f0e8da; stroke-width: 0.8; }",
            ]
        )
    styles.extend(
        [
            f".measure-no {{ font-size: {_px(options.measure_number_font_size)}px; fill: #333; font-weight: 600; }}",
            f".measure-attribute {{ font-size: {_px(options.measure_attribute_font_size)}px; fill: #333; font-weight: 600; }}",
            f".repeat-count {{ font-size: {_px(options.repeat_count_font_size)}px; fill: #333; font-weight: 600; }}",
            ".duration-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
            ".extension-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
            ".tie { fill: none; stroke: #171717; stroke-width: 1.5; stroke-linecap: round; }",
            ".slur { fill: none; stroke: #171717; stroke-width: 1.3; stroke-linecap: round; }",
            ".slide { fill: none; stroke: #171717; stroke-width: 1.45; stroke-linecap: round; }",
            ".tuplet-bracket { fill: none; stroke: #171717; stroke-width: 1.2; stroke-linecap: round; stroke-linejoin: round; }",
            f".tuplet-number {{ font-size: {_px(options.tuplet_font_size)}px; fill: #171717; font-weight: 650; }}",
            ".octave-dot, .rhythm-dot { fill: #171717; }",
            ".generated { fill: #818181; }",
            ".error { fill: #b3261e; }",
        ]
    )
    if not standalone_page:
        styles.append(".ocr-text { font-size: 20px; fill: #333; }")
    styles.extend(
        [
            f".lyric {{ font-size: {_px(options.lyric_font_size)}px; fill: #5f5a52; }}",
            f".annotation {{ font-size: {_px(options.lyric_font_size)}px; fill: #202020; }}",
            f".dynamic {{ font-size: {_px(options.dynamic_font_size)}px; font-style: italic; font-weight: 650; }}",
            f".ornament {{ font-size: {_px(options.ornament_font_size)}px; fill: #171717; }}",
            f".technical {{ font-size: {_px(options.technical_font_size)}px; fill: #171717; }}",
            f".technique-mark {{ font-size: {_px(options.technique_font_size)}px; fill: #171717; font-weight: 650; }}",
            ".articulation { stroke: #171717; fill: none; stroke-width: 1.5; stroke-linecap: round; }",
            ".staccato { fill: #171717; stroke: none; }",
            ".performance-symbol { fill: none; stroke: #171717; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }",
            ".performance-symbol-fill { fill: #171717; stroke: none; }",
            ".playback-note.playback-current .note, .playback-note.playback-current .accidental, .playback-note.playback-current .dynamic, .playback-note.playback-current .ornament, .playback-note.playback-current .technical, .playback-note.playback-current .technique-mark, .playback-note.playback-current .lyric { fill: #d97706; }",
            ".playback-note.playback-current .duration-line, .playback-note.playback-current .extension-line, .playback-note.playback-current .tie, .playback-note.playback-current .slur, .playback-note.playback-current .articulation, .playback-note.playback-current .performance-symbol { stroke: #d97706; }",
            ".playback-note.playback-current .octave-dot, .playback-note.playback-current .rhythm-dot, .playback-note.playback-current .staccato, .playback-note.playback-current .performance-symbol-fill { fill: #d97706; }",
            ".playback-note.playback-current .technique-mark { stroke: #d97706; }",
        ]
    )
    styles.append(
        ".ocr-overlay { font-size: 18px; fill: #202020; }"
        if standalone_page
        else ".ocr-overlay { fill: #202020; }"
    )
    return styles


def _svg_opening(
    options: RenderOptions, width: int, height: int, *, standalone_page: bool
) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        "<style>",
        *_svg_styles(options, standalone_page=standalone_page),
        "</style>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#fffdf7"/>',
    ]


def _svg_header(
    options: RenderOptions, height: int, title: str, meta: str
) -> list[str]:
    return [
        *_svg_opening(
            options,
            options.width,
            height,
            standalone_page=False,
        ),
        f'<text class="title" x="{options.width / 2}" y="{options.margin}" text-anchor="middle">{_esc(title)}</text>',
        f'<text class="meta" x="{options.margin}" y="{options.margin + 48}">{_esc(meta)}</text>',
    ]


def _svg_page_header(options: RenderOptions, width: int, height: int) -> list[str]:
    return _svg_opening(options, width, height, standalone_page=True)
