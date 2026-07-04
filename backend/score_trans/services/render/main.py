from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ...domain.jianpu import parse_jianpu_score
from ...domain.performance_marks import event_mark_ids, get_performance_mark
from ...domain.text_attachments import first_ocr_measure_number
from ...models.common.types import MeasureNumberMode
from ...models.score import JianpuScore, TextBlock
from .drawing.measure import _render_measure
from .drawing.spanners import _finish_open_spanners
from .drawing.text import _render_positioned_text_blocks
from .layout.measure import _score_measure_layout
from .layout.rows import _layout_rows
from .models.layout import MeasureLayout
from .options import A4_RENDER_THEME, A4RenderTheme, RenderOptions
from .parsing.tokens import _parse_chord_token, _parse_note
from .svg.header import _svg_header, _svg_page_header
from .utils.text import _esc, _strip_legacy_text_directives

A4_PAGE_WIDTH = 1240
A4_PAGE_HEIGHT = 1754
A4_STAFF_SPACE = 21.0
A4_MARGIN = 64
A4_LINE_HEIGHT = 160
A4_ROW_BOTTOM_EXTENT = 80
A4_MIN_MEASURE_WIDTH = 250
A4_NOTE_MIN_GAP = 5.6
A4_SHORT_NOTE_GAP_RATIO = 0.25
A4_SHORT_NOTE_SLOT_WIDTH_RATIO = 0.72
A4_TUPLET_GAP_RATIO = 0.12
A4_TUPLET_SLOT_WIDTH_RATIO = 0.48
A4_DURATION_SPACING_RATIO = 1.0
A4_BEAT_GAP = 8
A4_CHORD_GAP = 32.0
A4_CHORD_TOKEN_WIDTH = 34.0
A4_TITLE_BLOCK_HEIGHT = 116
A4_BOTTOM_MARGIN = 50


@dataclass(slots=True)
class A4MeasureRange:
    source_page_index: int
    start_measure_number: int | None
    end_measure_number: int | None


@dataclass(slots=True)
class RenderedA4Page:
    svg: str
    measure_ranges: list[A4MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None


@dataclass(slots=True)
class RenderedA4FilePage:
    path: Path
    measure_ranges: list[A4MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None


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
    clean_text = _strip_legacy_text_directives(jianpu_text)
    score = parse_jianpu_score(clean_text, title=title)
    positioned_blocks = text_blocks or []
    score.text_blocks.extend(positioned_blocks)
    if start_measure_number is not None:
        measure_start = start_measure_number
    else:
        measure_start = first_ocr_measure_number(positioned_blocks) or 1
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
        line_height=max(_content_min_line_height(layouts), int(line_height)),
        min_measure_width=base_options.min_measure_width,
        max_measure_width=max(base_options.max_measure_width, width - margin * 2),
        beat_gap=base_options.beat_gap,
        show_measure_numbers=base_options.show_measure_numbers,
        measure_number_mode=base_options.measure_number_mode,
    )
    rows = _layout_rows(layouts, page_options)

    out = _svg_page_header(page_options, width, height)
    y = top
    previous_attributes: tuple[str, int, int] | None = None
    for row in rows:
        x = float(page_options.margin)
        open_tie = None
        open_slur = None
        open_slide = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur, open_slide = _render_measure(
                measure,
                x,
                int(y),
                measure.width,
                page_options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                show_measure_number=_should_show_measure_number(page_options, index),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(
                int(y),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
                options=page_options,
            )
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
        line_height=max(_content_min_line_height(layouts), int(line_height)),
        min_measure_width=base_options.min_measure_width,
        max_measure_width=max(base_options.max_measure_width, width - margin * 2),
        beat_gap=base_options.beat_gap,
        show_measure_numbers=base_options.show_measure_numbers,
        measure_number_mode=base_options.measure_number_mode,
    )
    rows = _layout_rows(layouts, page_options)

    out = _svg_page_header(page_options, width, height)
    y = top
    previous_attributes: tuple[str, int, int] | None = None
    for row in rows:
        x = float(page_options.margin)
        open_tie = None
        open_slur = None
        open_slide = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur, open_slide = _render_measure(
                measure,
                x,
                int(y),
                measure.width,
                page_options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                show_measure_number=_should_show_measure_number(page_options, index),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(
                int(y),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
                options=page_options,
            )
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


def render_jianpu_a4_svgs(
    jianpu_text: str | JianpuScore,
    options: RenderOptions | None = None,
) -> list[str]:
    if isinstance(jianpu_text, JianpuScore):
        return render_score_a4_svgs(jianpu_text, options)
    options = options or RenderOptions()
    score = parse_jianpu_score(jianpu_text, title=options.title)
    return render_score_a4_svgs(score, options)


def render_score_a4_svgs(
    score: JianpuScore, options: RenderOptions | None = None
) -> list[str]:
    return render_scores_a4_svgs([score], options)


def render_scores_a4_svgs(
    scores: list[JianpuScore],
    options: RenderOptions | None = None,
    *,
    page_text_blocks: dict[int, list[TextBlock]] | None = None,
) -> list[str]:
    return [
        page.svg
        for page in render_scores_a4_pages(
            scores,
            options,
            page_text_blocks=page_text_blocks,
        )
    ]


def render_scores_a4_pages(
    scores: list[JianpuScore],
    options: RenderOptions | None = None,
    *,
    page_text_blocks: dict[int, list[TextBlock]] | None = None,
) -> list[RenderedA4Page]:
    if len(scores) > 1 and scores[0].part_count > 1:
        return render_multi_part_scores_a4_pages(
            scores, options, page_text_blocks=page_text_blocks
        )
    first_score = next((score for score in scores if score.measures), None)
    if first_score is None:
        first_score = scores[0] if scores else JianpuScore()
    page_options = _a4_render_options(options, title=first_score.title)
    layouts = _scores_layouts_with_playback_indices(scores, page_options)
    page_options = replace(
        page_options,
        line_height=max(page_options.line_height, _content_min_line_height(layouts)),
    )
    rows = _layout_rows(layouts, page_options)
    row_pages = _paginate_rows(rows, page_options)
    meta = _score_meta(first_score)
    text_blocks_by_page = page_text_blocks or {}
    pages: list[RenderedA4Page] = []
    for index, page_rows in enumerate(row_pages):
        note_start, note_end = _note_index_range_for_rows(page_rows)
        pages.append(
            RenderedA4Page(
                svg=_render_a4_page(
                    page_rows,
                    page_options,
                    first_score.title,
                    meta,
                    page_index=index,
                    page_count=len(row_pages),
                    text_blocks=text_blocks_by_page.get(index, []),
                ),
                measure_ranges=_measure_ranges_for_rows(page_rows),
                note_index_start=note_start,
                note_index_end=note_end,
            )
        )
    return pages


def render_score_a4_pages_to_files(
    score: JianpuScore,
    output_path: Path,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> list[RenderedA4FilePage]:
    return render_scores_a4_pages_to_files(
        [score],
        output_path,
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )


def render_scores_a4_pages_to_files(
    scores: list[JianpuScore],
    output_path: Path,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> list[RenderedA4FilePage]:
    return render_scores_a4_page_results_to_files(
        scores,
        output_path,
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )


def render_scores_a4_page_results_to_files(
    scores: list[JianpuScore],
    output_path: Path,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
    *,
    page_text_blocks: dict[int, list[TextBlock]] | None = None,
) -> list[RenderedA4FilePage]:
    base_title = title or next((score.title for score in scores if score.title), "简谱")
    options = _render_options(
        title=base_title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )
    pages = render_scores_a4_pages(scores, options, page_text_blocks=page_text_blocks)
    paths = _write_svg_pages([page.svg for page in pages], output_path)
    return [
        RenderedA4FilePage(
            path=path,
            measure_ranges=page.measure_ranges,
            note_index_start=page.note_index_start,
            note_index_end=page.note_index_end,
        )
        for path, page in zip(paths, pages, strict=True)
    ]


def render_jianpu_file_to_svg(
    input_path: Path,
    output_path: Path,
    title: str = "简谱",
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> Path:
    options = _render_options(
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )
    svg = render_jianpu_svg(input_path.read_text(encoding="utf-8"), options)
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
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> Path:
    options = _render_options(
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )
    svg = render_jianpu_page_svg(
        input_path.read_text(encoding="utf-8"),
        page_width=page_width,
        page_height=page_height,
        title=title,
        text_blocks=text_blocks,
        start_measure_number=start_measure_number,
        options=options,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_score_file_to_svg(
    score: JianpuScore,
    output_path: Path,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> Path:
    options = _render_options(
        title=title or score.title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )
    svg = render_score_svg(score, options)
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
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> Path:
    options = _render_options(
        title=title or score.title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
    )
    svg = render_score_page_svg(
        score,
        page_width=page_width,
        page_height=page_height,
        title=title,
        options=options,
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
    options = replace(
        options,
        line_height=max(options.line_height, _content_min_line_height(layouts)),
    )
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
        open_slide = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur, open_slide = _render_measure(
                measure,
                x,
                y,
                measure.width,
                options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                show_measure_number=_should_show_measure_number(options, index),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(
                int(y),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
                options=options,
            )
        )
        y += options.line_height
    if footer_text:
        out.append(
            f'<text class="ocr-text" x="{options.margin}" y="{height - options.margin + 8}">{_esc(footer_text)}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def _content_min_line_height(layouts: list[MeasureLayout]) -> int:
    max_upper_extent = 0.0
    for measure in layouts:
        for beat in measure.beats:
            for item in beat.items:
                mark_ids = event_mark_ids(
                    list(
                        item.articulations
                        or ([item.articulation] if item.articulation else [])
                    ),
                    list(item.ornaments),
                    list(item.technical),
                )
                upper_extent = sum(
                    mark.visual_height + mark.stack_gap
                    for mark_id in mark_ids
                    if (mark := get_performance_mark(mark_id)) is not None
                    and mark.placement == "above"
                )
                max_upper_extent = max(max_upper_extent, upper_extent)
    return max(108, int(96 + max_upper_extent))


def _a4_render_options(
    options: RenderOptions | None,
    *,
    title: str | None = None,
    theme: A4RenderTheme = A4_RENDER_THEME,
) -> RenderOptions:
    base = options or RenderOptions(title=title or "简谱")
    mode = base.measure_number_mode
    return RenderOptions(
        title=title or base.title,
        width=A4_PAGE_WIDTH,
        margin=A4_MARGIN,
        measure_width=base.measure_width,
        line_height=A4_LINE_HEIGHT,
        font_family=base.font_family,
        min_measure_width=A4_MIN_MEASURE_WIDTH,
        max_measure_width=max(A4_MIN_MEASURE_WIDTH, A4_PAGE_WIDTH - A4_MARGIN * 2),
        beat_gap=A4_BEAT_GAP,
        staff_space=A4_STAFF_SPACE,
        note_min_gap=A4_NOTE_MIN_GAP,
        short_note_gap_ratio=A4_SHORT_NOTE_GAP_RATIO,
        short_note_slot_width_ratio=A4_SHORT_NOTE_SLOT_WIDTH_RATIO,
        tuplet_gap_ratio=A4_TUPLET_GAP_RATIO,
        tuplet_slot_width_ratio=A4_TUPLET_SLOT_WIDTH_RATIO,
        duration_spacing_ratio=A4_DURATION_SPACING_RATIO,
        chord_gap=A4_CHORD_GAP,
        chord_token_width=A4_CHORD_TOKEN_WIDTH,
        note_font_size=theme.note_font_size,
        accidental_font_size=theme.accidental_font_size,
        measure_number_font_size=theme.measure_number_font_size,
        measure_attribute_font_size=theme.measure_attribute_font_size,
        repeat_count_font_size=theme.repeat_count_font_size,
        tuplet_font_size=theme.tuplet_font_size,
        lyric_font_size=theme.lyric_font_size,
        dynamic_font_size=theme.dynamic_font_size,
        ornament_font_size=theme.ornament_font_size,
        technical_font_size=theme.technical_font_size,
        technique_font_size=theme.technique_font_size,
        compact_measure_layout=True,
        show_beat_guides=base.show_beat_guides,
        show_staff_guides=base.show_staff_guides,
        show_measure_numbers=base.show_measure_numbers and mode != "none",
        measure_number_mode=mode,
    )


def _paginate_rows(
    rows: list[list[MeasureLayout]], options: RenderOptions
) -> list[list[list[MeasureLayout]]]:
    if not rows:
        return [[]]
    top = _a4_score_top(options)
    bottom = A4_BOTTOM_MARGIN
    baseline_span = max(
        0,
        A4_PAGE_HEIGHT - top - bottom - A4_ROW_BOTTOM_EXTENT,
    )
    rows_per_page = max(1, int(baseline_span // options.line_height))
    return [
        rows[index : index + rows_per_page]
        for index in range(0, len(rows), rows_per_page)
    ]


def _a4_score_top(options: RenderOptions) -> int:
    return int(options.margin + A4_TITLE_BLOCK_HEIGHT)


def _render_a4_page(
    rows: list[list[MeasureLayout]],
    options: RenderOptions,
    title: str,
    meta: str,
    *,
    page_index: int,
    page_count: int,
    text_blocks: list[TextBlock] | None = None,
) -> str:
    out = _svg_header(options, A4_PAGE_HEIGHT, title, meta)
    y = _a4_score_top(options)
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
        open_slide = None
        for index, measure in enumerate(row):
            attribute_text, previous_attributes = _measure_attribute_text(
                measure, previous_attributes
            )
            svg_lines, open_tie, open_slur, open_slide = _render_measure(
                measure,
                x,
                y,
                measure.width,
                options,
                draw_start_bar=index == 0,
                attribute_text=attribute_text,
                show_measure_number=_should_show_measure_number(options, index),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
            )
            out.extend(svg_lines)
            x += measure.width
        out.extend(
            _finish_open_spanners(
                int(y),
                open_tie=open_tie,
                open_slur=open_slur,
                open_slide=open_slide,
                options=options,
            )
        )
        y += options.line_height
    if page_count > 1:
        out.append(
            f'<text class="meta" x="{A4_PAGE_WIDTH / 2:.1f}" '
            f'y="{A4_PAGE_HEIGHT - 34}" text-anchor="middle">'
            f"{page_index + 1} / {page_count}</text>"
        )
    out.extend(
        _render_positioned_text_blocks(
            text_blocks or [],
            A4_PAGE_WIDTH,
            A4_PAGE_HEIGHT,
            include_measure_numbers=False,
        )
    )
    out.append("</svg>")
    return "\n".join(out)


def _note_index_range_for_rows(
    rows: list[list[MeasureLayout]],
) -> tuple[int | None, int | None]:
    indices = [
        item.playback_index
        for row in rows
        for measure in row
        for beat in measure.beats
        for item in beat.items
        if item.playback_index is not None
    ]
    if not indices:
        return None, None
    return min(indices), max(indices)


def _measure_ranges_for_rows(
    rows: list[list[MeasureLayout]],
) -> list[A4MeasureRange]:
    ranges: list[A4MeasureRange] = []
    for row in rows:
        for layout in row:
            source = layout.source
            source_index = getattr(source, "source_page_index", None)
            if source_index is None:
                source_index = 0
            start = _measure_number_as_int(getattr(source, "display_number", None))
            if start is None:
                start = _measure_number_as_int(getattr(source, "source_number", None))
            repeat_count = max(1, int(getattr(source, "repeat_count", 1) or 1))
            end = start + repeat_count - 1 if start is not None else None
            _append_measure_range(ranges, int(source_index), start, end)
    return ranges


def _append_measure_range(
    ranges: list[A4MeasureRange],
    source_page_index: int,
    start: int | None,
    end: int | None,
) -> None:
    if not ranges or ranges[-1].source_page_index != source_page_index:
        ranges.append(A4MeasureRange(source_page_index, start, end))
        return
    previous = ranges[-1]
    if previous.start_measure_number is None or start is None:
        previous.start_measure_number = previous.start_measure_number or start
        previous.end_measure_number = previous.end_measure_number or end
        return
    previous.end_measure_number = max(
        previous.end_measure_number or previous.start_measure_number, end or start
    )


def _measure_number_as_int(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _write_svg_pages(svgs: list[str], output_path: Path) -> list[Path]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, svg in enumerate(svgs):
        page_path = (
            output_path
            if index == 0
            else output_path.with_name(
                f"{output_path.stem}_p{index + 1}{output_path.suffix}"
            )
        )
        page_path.write_text(svg, encoding="utf-8")
        paths.append(page_path)
    return paths


def _score_meta(score: JianpuScore) -> str:
    first_measure = score.measures[0] if score.measures else None
    key = (
        getattr(first_measure, "target_key", score.target_key)
        if first_measure
        else score.target_key
    )
    beats = (
        getattr(first_measure, "beats_per_measure", score.beats)
        if first_measure
        else score.beats
    )
    beat_type = (
        getattr(first_measure, "beat_type", score.beat_type)
        if first_measure
        else score.beat_type
    )
    return f"1={key}    {beats}/{beat_type}"


def _render_options(
    *,
    title: str,
    show_measure_numbers: bool | None = None,
    measure_number_mode: MeasureNumberMode | None = None,
) -> RenderOptions:
    mode = measure_number_mode or ("none" if show_measure_numbers is False else "all")
    return RenderOptions(
        title=title,
        show_measure_numbers=mode != "none",
        measure_number_mode=mode,
    )


def _should_show_measure_number(options: RenderOptions, measure_index: int) -> bool:
    if not options.show_measure_numbers or options.measure_number_mode == "none":
        return False
    if options.measure_number_mode == "row_start":
        return measure_index == 0
    return True


def _score_layouts_with_playback_indices(
    score: JianpuScore, options: RenderOptions
) -> list[MeasureLayout]:
    return _scores_layouts_with_playback_indices([score], options)


def _scores_layouts_with_playback_indices(
    scores: list[JianpuScore], options: RenderOptions
) -> list[MeasureLayout]:
    layouts: list[MeasureLayout] = []
    playback_index = 0
    for source_page_index, score in enumerate(scores):
        for measure in score.measures:
            if measure.source_page_index is None:
                measure.source_page_index = source_page_index
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


def render_multi_part_scores_a4_pages(
    scores: list[JianpuScore],
    options: RenderOptions | None = None,
    *,
    page_text_blocks: dict[int, list[TextBlock]] | None = None,
) -> list[RenderedA4Page]:
    part_count = len(scores)
    measure_counts = [len(score.measures) for score in scores]
    if len(set(measure_counts)) > 1:
        details = "、".join(
            f"{score.part_name or f'声部{index + 1}'}={measure_counts[index]}"
            for index, score in enumerate(scores)
        )
        raise ValueError(f"各声部小节数量不一致：{details}")
    first_score = next((score for score in scores if score.measures), None)
    if first_score is None:
        first_score = scores[0] if scores else JianpuScore()
    page_options = _a4_render_options(options, title=first_score.title)

    all_part_layouts: list[list[MeasureLayout]] = []
    playback_index = 0
    for part_idx, score in enumerate(scores):
        part_layouts: list[MeasureLayout] = []
        for measure in score.measures:
            if measure.source_page_index is None:
                measure.source_page_index = part_idx
            layout = _score_measure_layout(measure, page_options)
            for beat in layout.beats:
                for item in beat.items:
                    if not _is_playable_note_token(item.token):
                        continue
                    item.playback_index = playback_index
                    playback_index += 1
            part_layouts.append(layout)
        all_part_layouts.append(part_layouts)

    max_measures = max((len(pl) for pl in all_part_layouts), default=0)
    for i in range(max_measures):
        max_ideal = 0.0
        max_min = 0.0
        for part_layouts in all_part_layouts:
            if i < len(part_layouts):
                layout = part_layouts[i]
                max_ideal = max(max_ideal, layout.ideal_width or layout.width)
                max_min = max(max_min, layout.min_width or layout.width)
        for part_layouts in all_part_layouts:
            if i < len(part_layouts):
                layout = part_layouts[i]
                layout.ideal_width = max_ideal
                layout.min_width = max_min

    first_part_layouts = all_part_layouts[0] if all_part_layouts else []
    page_options = replace(
        page_options,
        line_height=max(
            page_options.line_height, _content_min_line_height(first_part_layouts)
        ),
    )
    rows = _layout_rows(first_part_layouts, page_options)

    layout_id_to_index = {id(layout): i for i, layout in enumerate(first_part_layouts)}
    row_measure_indices: list[list[int]] = []
    for row in rows:
        indices = []
        for layout in row:
            idx = layout_id_to_index.get(id(layout))
            if idx is not None:
                indices.append(idx)
        row_measure_indices.append(indices)

    all_part_rows: list[list[list[MeasureLayout]]] = [rows]
    for part_idx in range(1, part_count):
        part_layouts = all_part_layouts[part_idx]
        part_rows: list[list[MeasureLayout]] = [[] for _ in rows]
        for i, layout in enumerate(part_layouts):
            for row_idx, indices in enumerate(row_measure_indices):
                if i in indices:
                    src_layout = rows[row_idx][indices.index(i)]
                    layout.width = src_layout.width
                    part_rows[row_idx].append(layout)
                    break
        all_part_rows.append(part_rows)

    effective_row_height = page_options.line_height * part_count
    top = _a4_score_top(page_options)
    bottom = A4_BOTTOM_MARGIN
    baseline_span = max(0, A4_PAGE_HEIGHT - top - bottom - A4_ROW_BOTTOM_EXTENT)
    rows_per_page = max(1, int(baseline_span // effective_row_height))

    meta = _score_meta(first_score)
    text_blocks_by_page = page_text_blocks or {}
    pages: list[RenderedA4Page] = []
    page_count = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
    for page_idx in range(page_count):
        start = page_idx * rows_per_page
        end = min(start + rows_per_page, len(rows))
        page_rows_slice = list(range(start, end))

        page_rows_all_parts = [
            part_rows[row_idx]
            for part_rows in all_part_rows
            for row_idx in page_rows_slice
            if row_idx < len(part_rows)
        ]
        note_start, note_end = _note_index_range_for_rows(page_rows_all_parts)

        pages.append(
            RenderedA4Page(
                svg=_render_multi_part_a4_page(
                    all_part_rows,
                    page_rows_slice,
                    page_options,
                    first_score.title,
                    meta,
                    page_index=page_idx,
                    page_count=page_count,
                    part_names=[s.part_name for s in scores],
                    text_blocks=text_blocks_by_page.get(page_idx, []),
                ),
                measure_ranges=_measure_ranges_for_rows(page_rows_all_parts),
                note_index_start=note_start,
                note_index_end=note_end,
            )
        )
    return pages


def _render_multi_part_a4_page(
    all_part_rows: list[list[list[MeasureLayout]]],
    page_rows_slice: list[int],
    options: RenderOptions,
    title: str,
    meta: str,
    *,
    page_index: int,
    page_count: int,
    part_names: list[str],
    text_blocks: list[TextBlock] | None = None,
) -> str:
    out = _svg_header(options, A4_PAGE_HEIGHT, title, meta)
    y = _a4_score_top(options)
    part_count = len(all_part_rows)
    line_height = options.line_height
    previous_attrs: list[tuple[str, int, int] | None] = [None] * part_count

    for row_idx in page_rows_slice:
        bracket_x = options.margin - 22
        bracket_top = y + 24
        bracket_bottom = y + (part_count - 1) * line_height + 60
        out.append(
            f'<path d="M {bracket_x} {bracket_top} '
            f"Q {bracket_x - 8} {(bracket_top + bracket_bottom) / 2:.1f} "
            f'{bracket_x} {bracket_bottom}" '
            f'fill="none" stroke="currentColor" stroke-width="2"/>'
        )

        for part_idx in range(part_count):
            part_rows = all_part_rows[part_idx]
            if row_idx >= len(part_rows):
                continue
            row = part_rows[row_idx]
            if not row:
                continue
            y_part = y + part_idx * line_height

            row_width = sum(measure.width for measure in row)
            if options.show_staff_guides:
                out.append(
                    f'<line class="staff-line" x1="{options.margin}" '
                    f'y1="{y_part + 44}" '
                    f'x2="{options.margin + row_width:.1f}" '
                    f'y2="{y_part + 44}"/>'
                )

            if part_idx < len(part_names) and part_names[part_idx]:
                name_x = bracket_x - 10
                name_y = y_part + 44
                out.append(
                    f'<text class="part-name" x="{name_x}" y="{name_y}" '
                    f'text-anchor="middle" font-size="14" '
                    f'transform="rotate(-90 {name_x} {name_y})">'
                    f"{_esc(part_names[part_idx])}</text>"
                )

            x = float(options.margin)
            open_tie = None
            open_slur = None
            open_slide = None
            for index, measure in enumerate(row):
                attribute_text, current_attrs = _measure_attribute_text(
                    measure, previous_attrs[part_idx]
                )
                previous_attrs[part_idx] = current_attrs
                show_number = (
                    _should_show_measure_number(options, index)
                    if part_idx == 0
                    else False
                )
                svg_lines, open_tie, open_slur, open_slide = _render_measure(
                    measure,
                    x,
                    int(y_part),
                    measure.width,
                    options,
                    draw_start_bar=index == 0,
                    attribute_text=attribute_text,
                    show_measure_number=show_number,
                    open_tie=open_tie,
                    open_slur=open_slur,
                    open_slide=open_slide,
                )
                out.extend(svg_lines)
                x += measure.width
            out.extend(
                _finish_open_spanners(
                    int(y_part),
                    open_tie=open_tie,
                    open_slur=open_slur,
                    open_slide=open_slide,
                    options=options,
                )
            )

        y += line_height * part_count

    if page_count > 1:
        out.append(
            f'<text class="meta" x="{A4_PAGE_WIDTH / 2:.1f}" '
            f'y="{A4_PAGE_HEIGHT - 34}" text-anchor="middle">'
            f"{page_index + 1} / {page_count}</text>"
        )
    out.extend(
        _render_positioned_text_blocks(
            text_blocks or [],
            A4_PAGE_WIDTH,
            A4_PAGE_HEIGHT,
            include_measure_numbers=False,
        )
    )
    out.append("</svg>")
    return "\n".join(out)
