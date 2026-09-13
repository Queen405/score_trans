"""Public rendering facade backed exclusively by the publication engine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from ...domain.jianpu import parse_jianpu_score
from ...domain.parse.jianpu_text import (
    ParsedJianpuPart,
    _assign_measure_number_bases,
    parse_jianpu_parts,
)
from ...models.common.errors import RenderError
from ...models.score import JianpuScore
from .engraving.renderer import MeasureRange, PublicationPage, PublicationRenderer
from .engraving.style import PublicationStyle
from .options import A4LayoutOptions, RenderOptions

A4_PAGE_WIDTH = 1240
A4_PAGE_HEIGHT = 1754


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
    note_group_start: int | None = None
    note_group_end: int | None = None
    playback_start_tick: int | None = None
    playback_end_tick: int | None = None
    layout_key: str = ""


@dataclass(slots=True)
class RenderedA4FilePage:
    path: Path
    measure_ranges: list[A4MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None
    note_group_start: int | None = None
    note_group_end: int | None = None
    playback_start_tick: int | None = None
    playback_end_tick: int | None = None
    render_map_path: Path | None = None
    layout_key: str = ""


def render_jianpu_svg(
    jianpu_text: str | JianpuScore, options: RenderOptions | None = None
) -> str:
    options = options or RenderOptions()
    score = (
        jianpu_text
        if isinstance(jianpu_text, JianpuScore)
        else parse_jianpu_score(jianpu_text, title=options.title)
    )
    if (
        not isinstance(jianpu_text, JianpuScore)
        and score.title != "简谱"
        and options.title == "简谱"
    ):
        options = replace(options, title=score.title)
    return render_score_svg(score, options)


def render_live_measure_svg(
    jianpu_text: str,
    cursor_offset: int,
    options: RenderOptions | None = None,
) -> str:
    """Parse the full text for key/time/tempo context, then render only the
    single measure containing *cursor_offset*.

    多声部/多页文档按 // @part、// @page 切分，定位光标所在声部的小节；
    解析失败（编辑中间态）退化为旧的整篇小节线统计。"""
    options = options or RenderOptions(title="")
    try:
        parts = parse_jianpu_parts(jianpu_text, title=options.title)
    except Exception:  # noqa: BLE001 — 编辑中间态走旧逻辑
        parts = []
    if parts:
        return _render_live_part_measure(parts, cursor_offset, options)
    score = parse_jianpu_score(jianpu_text, title=options.title)
    if not score.measures:
        return render_score_svg(score, options)
    measure_index = jianpu_text.count("|", 0, max(0, cursor_offset))
    measure_index = min(measure_index, len(score.measures) - 1)
    single = replace(score, title="", measures=[score.measures[measure_index]])
    initial_number = (options.initial_measure_number or 1) + measure_index
    options = replace(options, initial_measure_number=initial_number)
    return render_score_svg(single, options)


def _render_live_part_measure(
    parts: list[ParsedJianpuPart],
    cursor_offset: int,
    options: RenderOptions,
) -> str:
    # cursor_offset 是编辑器（JS）的 UTF-16 偏移，与 part/measure 的
    # *_utf16 字段同单位。光标落在空白/标记行时取前方最近声部与小节。
    cursor = max(0, cursor_offset)
    part = parts[0]
    for candidate in parts:
        if candidate.body_start_utf16 <= cursor:
            part = candidate
        else:
            break
    score = part.score
    if not score.measures:
        return render_score_svg(score, options)
    measure_index = 0
    for index, measure in enumerate(score.measures):
        start = measure.source_start_utf16
        end = measure.source_end_utf16
        if end is not None and end <= cursor:
            measure_index = index + 1
        elif start is not None and start <= cursor:
            measure_index = index
    measure_index = min(measure_index, len(score.measures) - 1)
    _assign_measure_number_bases(
        parts, initial_measure_number=options.initial_measure_number or 1
    )
    initial_number = part.measure_number_base + sum(
        max(1, int(getattr(measure, "repeat_count", 1) or 1))
        for measure in score.measures[:measure_index]
    )
    single = replace(score, title="", measures=[score.measures[measure_index]])
    options = replace(options, initial_measure_number=initial_number)
    return render_score_svg(single, options)


def render_score_svg(score: JianpuScore, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions(title=score.title)
    style = _style_from_options(options, page_width=float(options.width))
    estimated_height = max(420.0, 270.0 + len(score.measures) * 150.0)
    style = replace(style, page_height=estimated_height)
    pages = PublicationRenderer(style).render_scores(
        [score],
        fit_content_height=True,
        title=options.title or score.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        initial_measure_number=options.initial_measure_number,
        show_title=options.show_title,
        show_page_number=options.show_page_number,
    )
    if len(pages) != 1:
        raise RenderError("单页渲染空间不足；请使用 A4 分页渲染入口")
    return pages[0].svg


def render_scores_svg(
    scores: list[JianpuScore], options: RenderOptions | None = None
) -> str:
    """多声部版本，与 render_score_svg 对应，页面高度按内容自动估算。"""
    first = scores[0] if scores else JianpuScore()
    options = options or RenderOptions(title=first.title)
    style = _style_from_options(options, page_width=float(options.width))
    measure_count = max((len(score.measures) for score in scores), default=0)
    part_count = max(len(scores), 1)
    estimated_height = max(420.0, 270.0 + measure_count * 150.0 * part_count)
    style = replace(style, page_height=estimated_height)
    pages = PublicationRenderer(style).render_scores(
        scores,
        fit_content_height=True,
        title=options.title or first.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        initial_measure_number=options.initial_measure_number,
        show_title=options.show_title,
        show_page_number=options.show_page_number,
    )
    if len(pages) != 1:
        raise RenderError("单页渲染空间不足；请使用 A4 分页渲染入口")
    return pages[0].svg


def render_scores_page_svg(
    scores: list[JianpuScore],
    *,
    page_width: float,
    page_height: float,
    options: RenderOptions | None = None,
) -> str:
    """多声部版本，与 render_score_page_svg 对应，使用固定页面尺寸。"""
    first = scores[0] if scores else JianpuScore()
    options = options or RenderOptions(title=first.title)
    style = _style_from_options(options, page_width=page_width, page_height=page_height)
    pages = PublicationRenderer(style).render_scores(
        scores,
        title=options.title or first.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        initial_measure_number=options.initial_measure_number,
    )
    if len(pages) != 1:
        raise RenderError("请求的页面尺寸无法容纳全部谱面内容")
    return pages[0].svg


def render_jianpu_page_svg(
    jianpu_text: str,
    *,
    page_width: float,
    page_height: float,
    title: str = "简谱",
    options: RenderOptions | None = None,
) -> str:
    score = parse_jianpu_score(jianpu_text, title=title)
    return render_score_page_svg(
        score,
        page_width=page_width,
        page_height=page_height,
        options=options or RenderOptions(title=title),
    )


def render_score_page_svg(
    score: JianpuScore,
    *,
    page_width: float,
    page_height: float,
    options: RenderOptions | None = None,
) -> str:
    options = options or RenderOptions(title=score.title)
    style = _style_from_options(options, page_width=page_width, page_height=page_height)
    pages = PublicationRenderer(style).render_scores(
        [score],
        title=options.title or score.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        initial_measure_number=options.initial_measure_number,
    )
    if len(pages) != 1:
        raise RenderError("请求的页面尺寸无法容纳全部谱面内容")
    return pages[0].svg


def render_scores_a4_pages(
    scores: list[JianpuScore],
    options: RenderOptions | None = None,
    layout: A4LayoutOptions | None = None,
) -> list[RenderedA4Page]:
    options = options or RenderOptions(title=(scores[0].title if scores else "简谱"))
    layout = layout or A4LayoutOptions()
    renderer = _a4_renderer(options, layout)
    pages = renderer.render_scores(
        scores,
        title=options.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        initial_measure_number=options.initial_measure_number,
    )
    return [_public_page(page) for page in pages]


def render_score_a4_pages_to_files(
    score: JianpuScore,
    output_path: Path,
    *,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
    layout: A4LayoutOptions | None = None,
    playback_group_offset: int = 0,
    playback_tick_offset: int = 0,
    show_title: bool = True,
) -> list[RenderedA4FilePage]:
    return render_scores_a4_pages_to_files(
        [score],
        output_path,
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
        initial_measure_number=initial_measure_number,
        layout=layout,
    )


def render_scores_a4_pages_to_files(
    scores: list[JianpuScore],
    output_path: Path,
    *,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
    layout: A4LayoutOptions | None = None,
) -> list[RenderedA4FilePage]:
    return render_scores_a4_page_results_to_files(
        scores,
        output_path,
        title=title,
        show_measure_numbers=show_measure_numbers,
        measure_number_mode=measure_number_mode,
        initial_measure_number=initial_measure_number,
        layout=layout,
    )


def render_scores_a4_page_results_to_files(
    scores: list[JianpuScore],
    output_path: Path,
    *,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
    layout: A4LayoutOptions | None = None,
    playback_group_offset: int = 0,
    playback_tick_offset: int = 0,
    show_title: bool = True,
    page_index_offset: int = 0,
) -> list[RenderedA4FilePage]:
    options = RenderOptions(
        title=title or (scores[0].title if scores else "简谱"),
        show_measure_numbers=show_measure_numbers is not False,
        measure_number_mode=measure_number_mode
        or ("none" if show_measure_numbers is False else "all"),
        initial_measure_number=initial_measure_number,
    )
    layout = layout or A4LayoutOptions()
    renderer = _a4_renderer(options, layout)
    pages = renderer.render_scores(
        scores,
        title=options.title,
        show_measure_numbers=options.show_measure_numbers,
        measure_number_mode=options.measure_number_mode,
        playback_group_offset=playback_group_offset,
        playback_tick_offset=playback_tick_offset,
        show_title=show_title,
        page_index_offset=page_index_offset,
    )
    paths = renderer.write_pages(pages, output_path)
    return [
        RenderedA4FilePage(
            path=path,
            measure_ranges=_ranges(page.measure_ranges),
            note_index_start=page.note_index_start,
            note_index_end=page.note_index_end,
            note_group_start=page.note_group_start,
            note_group_end=page.note_group_end,
            playback_start_tick=page.playback_start_tick,
            playback_end_tick=page.playback_end_tick,
            render_map_path=path.with_suffix(".render-map.json"),
            layout_key=layout.key,
        )
        for page, path in zip(pages, paths, strict=True)
    ]


def render_jianpu_file_to_svg(
    input_path: Path,
    output_path: Path,
    *,
    title: str = "简谱",
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    svg = render_jianpu_svg(
        input_path.read_text(encoding="utf-8"),
        RenderOptions(
            title=title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
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
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    svg = render_jianpu_page_svg(
        input_path.read_text(encoding="utf-8"),
        page_width=page_width,
        page_height=page_height,
        title=title,
        options=RenderOptions(
            title=title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_score_file_to_svg(
    score: JianpuScore,
    output_path: Path,
    *,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    svg = render_score_svg(
        score,
        RenderOptions(
            title=title or score.title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
    )
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
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    svg = render_score_page_svg(
        score,
        page_width=page_width,
        page_height=page_height,
        options=RenderOptions(
            title=title or score.title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_scores_file_to_svg(
    scores: list[JianpuScore],
    output_path: Path,
    *,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    """多声部版本，与 render_score_file_to_svg 对应。"""
    first = scores[0] if scores else JianpuScore()
    svg = render_scores_svg(
        scores,
        RenderOptions(
            title=title or first.title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_scores_page_file_to_svg(
    scores: list[JianpuScore],
    output_path: Path,
    *,
    page_width: float,
    page_height: float,
    title: str | None = None,
    show_measure_numbers: bool | None = None,
    measure_number_mode=None,
    initial_measure_number: int | None = 1,
) -> Path:
    """多声部版本，与 render_score_page_file_to_svg 对应。"""
    first = scores[0] if scores else JianpuScore()
    svg = render_scores_page_svg(
        scores,
        page_width=page_width,
        page_height=page_height,
        options=RenderOptions(
            title=title or first.title,
            show_measure_numbers=show_measure_numbers is not False,
            measure_number_mode=measure_number_mode or "all",
            initial_measure_number=initial_measure_number,
        ),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def _style_from_options(
    options: RenderOptions,
    *,
    page_width: float = A4_PAGE_WIDTH,
    page_height: float = A4_PAGE_HEIGHT,
) -> PublicationStyle:
    base = PublicationStyle(
        page_width=float(page_width), page_height=float(page_height)
    )
    margin = max(8.0, float(options.margin))
    return replace(
        base,
        margin_left=margin if page_width != A4_PAGE_WIDTH else base.margin_left,
        margin_right=margin if page_width != A4_PAGE_WIDTH else base.margin_right,
        note_size=options.note_font_size,
        accidental_size=options.accidental_font_size,
        lyric_size=options.lyric_font_size,
        minimum_measure_width=float(options.min_measure_width),
        minimum_event_gap=float(options.note_min_gap),
        font_family=options.font_family,
    )


def _a4_renderer(
    options: RenderOptions, layout: A4LayoutOptions
) -> PublicationRenderer:
    scale = layout.content_scale
    base = _style_from_options(options)
    style = replace(
        base,
        page_width=base.page_width / scale,
        page_height=base.page_height / scale,
        system_gap=base.system_gap * layout.system_gap_scale,
        short_note_gap_scale=layout.short_note_gap_scale,
        beat_boundary_gap=base.beat_boundary_gap * layout.beat_gap_scale,
    )
    return PublicationRenderer(
        style,
        coordinate_scale=scale,
        layout_key=layout.key,
    )


def _public_page(page: PublicationPage) -> RenderedA4Page:
    return RenderedA4Page(
        svg=page.svg,
        measure_ranges=_ranges(page.measure_ranges),
        note_index_start=page.note_index_start,
        note_index_end=page.note_index_end,
        note_group_start=page.note_group_start,
        note_group_end=page.note_group_end,
        playback_start_tick=page.playback_start_tick,
        playback_end_tick=page.playback_end_tick,
        layout_key=page.scene.layout_key,
    )


def _ranges(ranges: list[MeasureRange]) -> list[A4MeasureRange]:
    return [
        A4MeasureRange(
            item.source_page_index, item.start_measure_number, item.end_measure_number
        )
        for item in ranges
    ]
