from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ...domain.jianpu import parse_jianpu_score
from ...models.score import JianpuScore, TextBlock
from .drawing.measure import _render_measure
from .drawing.spanners import _finish_open_spanners
from .drawing.text import _render_positioned_text_blocks
from .layout.measure import _score_measure_layout
from .layout.rows import _layout_rows
from .models.layout import MeasureLayout
from .options import RenderOptions
from .parsing.tokens import _parse_chord_token, _parse_note
from .svg.header import _svg_header, _svg_page_header
from .utils.helpers import _first_ocr_measure_number
from .utils.text import _esc, _extract_text_directives


def render_jianpu_svg(
    jianpu_text: str | JianpuScore, options: RenderOptions | None = None
) -> str:
    if isinstance(jianpu_text, JianpuScore):
        return render_score_svg(jianpu_text, options)
    options = options or RenderOptions()
    score = parse_jianpu_score(jianpu_text, title=options.title)
    return render_score_svg(score, options)


def render_jianpu_page_svg(
    jianpu_text: str,
    *,
    page_width: float,
    page_height: float,
    title: str = "简谱",
    text_blocks: list[TextBlock] | None = None,
    options: RenderOptions | None = None,
    start_measure_number: int | None = None,
) -> str:
    width = max(1, int(round(page_width)))
    height = max(1, int(round(page_height)))
    base_options = options or RenderOptions(title=title, width=width)
    margin = min(72, max(4, int(width * 0.045)))
    margin = min(margin, max(1, width // 6))
    clean_text, directive_blocks = _extract_text_directives(jianpu_text)
    score = parse_jianpu_score(clean_text, title=title)
    positioned_blocks = directive_blocks or (text_blocks or [])
    score.text_blocks.extend(positioned_blocks)
    if start_measure_number is not None:
        measure_start = start_measure_number
    else:
        measure_start = _first_ocr_measure_number(positioned_blocks) or 1
    current_number = measure_start
    for measure in score.measures:
        measure.display_number = current_number
        current_number += getattr(measure, "repeat_count", 1)
    layouts = _score_layouts_with_playback_indices(score, base_options)
    rows = _layout_rows(layouts, replace(base_options, width=width, margin=margin))
    top = max(78.0, height * 0.13)
    bottom = max(36.0, height * 0.08)
    available = max(120.0, height - top - bottom)
    line_height = available / max(1, len(rows))
    page_options = RenderOptions(
        title=title,
        width=width,
        margin=margin,
        line_height=max(108, int(line_height)),
        min_measure_width=base_options.min_measure_width,
        max_measure_width=max(base_options.max_measure_width, width - margin * 2),
        beat_gap=base_options.beat_gap,
        show_measure_numbers=base_options.show_measure_numbers,
    )
    rows = _layout_rows(layouts, page_options)

    out = _svg_page_header(page_options, width, height)
    y = top
    previous_attributes: tuple[str, int, int] | None = None
    for row in rows:
        x = float(page_options.margin)
        open_tie = None
        open_slur = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur = _render_measure(
                measure,
                x,
                int(y),
                measure.width,
                page_options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                open_tie=open_tie,
                open_slur=open_slur,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(int(y), open_tie=open_tie, open_slur=open_slur)
        )
        y += page_options.line_height
        if y > height - bottom:
            break
    out.extend(
        _render_positioned_text_blocks(
            positioned_blocks, width, height, include_measure_numbers=False
        )
    )
    out.append("</svg>")
    return "\n".join(out)


def render_score_svg(score: JianpuScore, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions(title=score.title)
    layouts = _score_layouts_with_playback_indices(score, options)
    text_blocks = [block.text for block in score.text_blocks if block.text]
    return _render_layouts(
        layouts,
        options,
        score.title,
        f"1={score.target_key}    {score.beats}/{score.beat_type}",
        footer_text="  ".join(text_blocks) if text_blocks else None,
    )


def render_score_page_svg(
    score: JianpuScore,
    *,
    page_width: float,
    page_height: float,
    title: str | None = None,
    options: RenderOptions | None = None,
) -> str:
    width = max(1, int(round(page_width)))
    height = max(1, int(round(page_height)))
    base_options = options or RenderOptions(title=title or score.title, width=width)
    margin = min(72, max(4, int(width * 0.045)))
    margin = min(margin, max(1, width // 6))
    layouts = _score_layouts_with_playback_indices(score, base_options)
    rows = _layout_rows(layouts, replace(base_options, width=width, margin=margin))
    top = max(78.0, height * 0.13)
    bottom = max(36.0, height * 0.08)
    available = max(120.0, height - top - bottom)
    line_height = available / max(1, len(rows))
    page_options = RenderOptions(
        title=title or score.title,
        width=width,
        margin=margin,
        line_height=max(108, int(line_height)),
        min_measure_width=base_options.min_measure_width,
        max_measure_width=max(base_options.max_measure_width, width - margin * 2),
        beat_gap=base_options.beat_gap,
        show_measure_numbers=base_options.show_measure_numbers,
    )
    rows = _layout_rows(layouts, page_options)

    out = _svg_page_header(page_options, width, height)
    y = top
    previous_attributes: tuple[str, int, int] | None = None
    for row in rows:
        x = float(page_options.margin)
        open_tie = None
        open_slur = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur = _render_measure(
                measure,
                x,
                int(y),
                measure.width,
                page_options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                open_tie=open_tie,
                open_slur=open_slur,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(int(y), open_tie=open_tie, open_slur=open_slur)
        )
        y += page_options.line_height
        if y > height - bottom:
            break
    out.extend(
        _render_positioned_text_blocks(
            score.text_blocks, width, height, include_measure_numbers=False
        )
    )
    out.append("</svg>")
    return "\n".join(out)


def render_jianpu_file_to_svg(
    input_path: Path, output_path: Path, title: str = "简谱"
) -> Path:
    svg = render_jianpu_svg(
        input_path.read_text(encoding="utf-8"), RenderOptions(title=title)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_jianpu_page_file_to_svg(
    input_path: Path,
    output_path: Path,
    *,
    page_width: float,
    page_height: float,
    title: str = "简谱",
    text_blocks: list[TextBlock] | None = None,
    start_measure_number: int | None = None,
) -> Path:
    svg = render_jianpu_page_svg(
        input_path.read_text(encoding="utf-8"),
        page_width=page_width,
        page_height=page_height,
        title=title,
        text_blocks=text_blocks,
        start_measure_number=start_measure_number,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_score_file_to_svg(
    score: JianpuScore, output_path: Path, title: str | None = None
) -> Path:
    svg = render_score_svg(score, RenderOptions(title=title or score.title))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_score_page_file_to_svg(
    score: JianpuScore,
    output_path: Path,
    *,
    page_width: float,
    page_height: float,
    title: str | None = None,
) -> Path:
    svg = render_score_page_svg(
        score, page_width=page_width, page_height=page_height, title=title
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def _render_layouts(
    layouts: list[MeasureLayout],
    options: RenderOptions,
    title: str,
    meta: str,
    footer_text: str | None = None,
) -> str:
    rows = _layout_rows(layouts, options)
    footer_height = 80 if footer_text else 0
    height = (
        options.margin * 2
        + 126
        + max(1, len(rows)) * options.line_height
        + footer_height
    )
    out = _svg_header(options, height, title, meta)
    y = options.margin + 126
    previous_attributes: tuple[str, int, int] | None = None
    for row in rows:
        row_width = sum(measure.width for measure in row)
        if options.show_staff_guides:
            out.append(
                f'<line class="staff-line" x1="{options.margin}" y1="{y + 44}" '
                f'x2="{options.margin + row_width:.1f}" y2="{y + 44}"/>'
            )
        x = float(options.margin)
        open_tie = None
        open_slur = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur = _render_measure(
                measure,
                x,
                y,
                measure.width,
                options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                open_tie=open_tie,
                open_slur=open_slur,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(int(y), open_tie=open_tie, open_slur=open_slur)
        )
        y += options.line_height
    if footer_text:
        out.append(
            f'<text class="ocr-text" x="{options.margin}" y="{height - options.margin + 8}">{_esc(footer_text)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def _score_layouts_with_playback_indices(
    score: JianpuScore, options: RenderOptions
) -> list[MeasureLayout]:
    layouts: list[MeasureLayout] = []
    playback_index = 0
    for measure in score.measures:
        layout = _score_measure_layout(measure, options)
        for beat in layout.beats:
            for item in beat.items:
                if not _is_playable_note_token(item.token):
                    continue
                item.playback_index = playback_index
                playback_index += 1
        layouts.append(layout)
    return layouts


def _measure_attribute_text(
    measure: MeasureLayout,
    previous: tuple[str, int, int] | None,
) -> tuple[str | None, tuple[str, int, int]]:
    source = measure.source
    key = getattr(source, "target_key", "C")
    beats = getattr(source, "beats_per_measure", 4)
    beat_type = getattr(source, "beat_type", 4)
    current = (key, beats, beat_type)
    if previous is None:
        return None, current
    parts: list[str] = []
    if key != previous[0]:
        parts.append(f"1={key}")
    if beats != previous[1] or beat_type != previous[2]:
        parts.append(f"{beats}/{beat_type}")
    return "  ".join(parts) if parts else None, current


def _is_playable_note_token(token: str) -> bool:
    work = token.strip().strip("()~")
    if not work or work == "-":
        return False
    if _parse_chord_token(work) is not None:
        return True
    note = _parse_note(work)
    return any(ch in "1234567" for ch in note.display)
