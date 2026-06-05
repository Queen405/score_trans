from __future__ import annotations

from ..options import RenderOptions
from ..utils.text import _esc


def _svg_header(options: RenderOptions, height: int, title: str, meta: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{options.width}" height="{height}" viewBox="0 0 {options.width} {height}">',
        "<defs>",
        "<style>",
        f"text {{ font-family: {options.font_family}; fill: #171717; letter-spacing: 0; }}",
        ".title { font-size: 40px; font-weight: 700; }",
        ".meta { font-size: 23px; }",
        ".note { font-size: 30px; font-weight: 650; }",
        ".accidental { font-size: 18px; font-weight: 400; }",
        ".bar { stroke: #252525; stroke-width: 1.6; stroke-linecap: square; }",
        ".beat-guide { stroke: #e2dacd; stroke-width: 0.8; stroke-dasharray: 2 10; }",
        ".staff-line { stroke: #f0e8da; stroke-width: 0.8; }",
        ".measure-no { font-size: 13px; fill: #868686; }",
        ".duration-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
        ".extension-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
        ".tie { fill: none; stroke: #171717; stroke-width: 1.5; stroke-linecap: round; }",
        ".slur { fill: none; stroke: #171717; stroke-width: 1.3; stroke-linecap: round; }",
        ".octave-dot, .rhythm-dot { fill: #171717; }",
        ".generated { fill: #818181; }",
        ".error { fill: #b3261e; }",
        ".ocr-text { font-size: 20px; fill: #333; }",
        ".lyric { font-size: 18px; fill: #5f5a52; }",
        ".dynamic { font-size: 22px; font-style: italic; font-weight: 650; }",
        ".ornament { font-size: 15px; fill: #171717; }",
        ".technical { font-size: 13px; fill: #171717; }",
        ".technique-mark { font-size: 16px; fill: #171717; font-weight: 650; }",
        ".articulation { stroke: #171717; fill: none; stroke-width: 1.5; stroke-linecap: round; }",
        ".ocr-overlay { fill: #202020; }",
        "</style>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#fffdf7"/>',
        f'<text class="title" x="{options.width / 2}" y="{options.margin}" text-anchor="middle">{_esc(title)}</text>',
        f'<text class="meta" x="{options.margin}" y="{options.margin + 48}">{_esc(meta)}</text>',
    ]


def _svg_page_header(options: RenderOptions, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        "<style>",
        f"text {{ font-family: {options.font_family}; fill: #171717; letter-spacing: 0; }}",
        ".note { font-size: 30px; font-weight: 650; }",
        ".accidental { font-size: 18px; font-weight: 400; }",
        ".bar { stroke: #252525; stroke-width: 1.6; stroke-linecap: square; }",
        ".measure-no { font-size: 13px; fill: #868686; }",
        ".duration-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
        ".extension-line { stroke: #171717; stroke-width: 1.8; stroke-linecap: round; }",
        ".tie { fill: none; stroke: #171717; stroke-width: 1.5; stroke-linecap: round; }",
        ".slur { fill: none; stroke: #171717; stroke-width: 1.3; stroke-linecap: round; }",
        ".octave-dot, .rhythm-dot { fill: #171717; }",
        ".generated { fill: #818181; }",
        ".lyric { font-size: 18px; fill: #5f5a52; }",
        ".dynamic { font-size: 22px; font-style: italic; font-weight: 650; }",
        ".ornament { font-size: 15px; fill: #171717; }",
        ".technical { font-size: 13px; fill: #171717; }",
        ".technique-mark { font-size: 16px; fill: #171717; font-weight: 650; }",
        ".articulation { stroke: #171717; fill: none; stroke-width: 1.5; stroke-linecap: round; }",
        ".ocr-overlay { font-size: 18px; fill: #202020; }",
        "</style>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#fffdf7"/>',
    ]
