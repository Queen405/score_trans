from __future__ import annotations

import html
import re
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..domain.models import JianpuEvent, JianpuPitch, JianpuScore, TextBlock


CHORD_GAP = 38
LOW_OCTAVE_DOT_OFFSET = 18
OCTAVE_DOT_GAP = 8


@dataclass(slots=True)
class RenderOptions:
    title: str = "简谱"
    width: int = 1600
    margin: int = 72
    measure_width: int = 330
    line_height: int = 180
    font_family: str = "Microsoft YaHei, SimSun, Arial, sans-serif"
    min_measure_width: int = 112
    max_measure_width: int = 1100
    beat_gap: int = 14
    show_beat_guides: bool = False
    show_staff_guides: bool = False
    show_measure_numbers: bool = True


@dataclass(slots=True)
class NoteShape:
    display: str
    slashes: int
    octave_up: int
    octave_down: int
    rank: float
    dotted: bool = False
    extension: int = 0


@dataclass(slots=True)
class RenderItem:
    token: str
    duration: Fraction
    generated: bool = False
    start: Fraction | None = None
    lyric: str | None = None
    tie_start: bool = False
    tie_stop: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    dynamic: str | None = None
    articulation: str | None = None
    articulations: list[str] = field(default_factory=list)
    ornaments: list[str] = field(default_factory=list)
    technical: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BeatLayout:
    items: list[RenderItem]
    width: float


@dataclass(slots=True)
class MeasureLayout:
    source: Any
    number: str | int
    beats: list[BeatLayout]
    width: float
    errors: list[str] = field(default_factory=list)


def render_jianpu_svg(jianpu_text: str | JianpuScore, options: RenderOptions | None = None) -> str:
    if isinstance(jianpu_text, JianpuScore):
        return render_score_svg(jianpu_text, options)
    options = options or RenderOptions()
    clean_text, _directives = _extract_text_directives(jianpu_text)
    key, time, body = _split_header(clean_text)
    beat_count = _beats_from_time(time)
    layouts = [
        _text_measure_layout(measure, index, beat_count, options)
        for index, measure in enumerate(_split_measures(body), start=1)
    ]
    return _render_layouts(layouts, options, options.title, f"1={key}    {time}")


def render_jianpu_page_svg(
    jianpu_text: str,
    *,
    page_width: float,
    page_height: float,
    title: str = "简谱",
    text_blocks: list[TextBlock] | None = None,
    options: RenderOptions | None = None,
) -> str:
    width = max(1, int(round(page_width)))
    height = max(1, int(round(page_height)))
    base_options = options or RenderOptions(title=title, width=width)
    margin = min(72, max(4, int(width * 0.045)))
    margin = min(margin, max(1, width // 6))
    clean_text, directive_blocks = _extract_text_directives(jianpu_text)
    positioned_blocks = directive_blocks or (text_blocks or [])
    key, time, body = _split_header(clean_text)
    beat_count = _beats_from_time(time)
    measure_start = _first_ocr_measure_number(positioned_blocks) or 1
    layouts = [
        _text_measure_layout(measure, index, beat_count, base_options)
        for index, measure in enumerate(_split_measures(body), start=measure_start)
    ]
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
    for row in rows:
        x = float(page_options.margin)
        for index, measure in enumerate(row):
            out.extend(_render_measure(measure, x, int(y), measure.width, page_options, draw_start_bar=index == 0))
            x += measure.width
        y += page_options.line_height
        if y > height - bottom:
            break
    out.extend(_render_positioned_text_blocks(positioned_blocks, width, height, include_measure_numbers=False))
    out.append("</svg>")
    return "\n".join(out)


def render_score_svg(score: JianpuScore, options: RenderOptions | None = None) -> str:
    options = options or RenderOptions(title=score.title)
    layouts = [_score_measure_layout(measure, options) for measure in score.measures]
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
    layouts = [_score_measure_layout(measure, base_options) for measure in score.measures]
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
    for row in rows:
        x = float(page_options.margin)
        for index, measure in enumerate(row):
            out.extend(_render_measure(measure, x, int(y), measure.width, page_options, draw_start_bar=index == 0))
            x += measure.width
        y += page_options.line_height
        if y > height - bottom:
            break
    out.extend(_render_positioned_text_blocks(score.text_blocks, width, height, include_measure_numbers=False))
    out.append("</svg>")
    return "\n".join(out)


def render_jianpu_file_to_svg(input_path: Path, output_path: Path, title: str = "简谱") -> Path:
    svg = render_jianpu_svg(input_path.read_text(encoding="utf-8"), RenderOptions(title=title))
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
) -> Path:
    svg = render_jianpu_page_svg(
        input_path.read_text(encoding="utf-8"),
        page_width=page_width,
        page_height=page_height,
        title=title,
        text_blocks=text_blocks,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")
    return output_path


def render_score_file_to_svg(score: JianpuScore, output_path: Path, title: str | None = None) -> Path:
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
    svg = render_score_page_svg(score, page_width=page_width, page_height=page_height, title=title)
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
    height = options.margin * 2 + 126 + max(1, len(rows)) * options.line_height + footer_height
    out = _svg_header(options, height, title, meta)
    y = options.margin + 126
    for row in rows:
        row_width = sum(measure.width for measure in row)
        if options.show_staff_guides:
            out.append(
                f'<line class="staff-line" x1="{options.margin}" y1="{y + 44}" '
                f'x2="{options.margin + row_width:.1f}" y2="{y + 44}"/>'
            )
        x = float(options.margin)
        for index, measure in enumerate(row):
            out.extend(_render_measure(measure, x, y, measure.width, options, draw_start_bar=index == 0))
            x += measure.width
        y += options.line_height
    if footer_text:
        out.append(f'<text class="ocr-text" x="{options.margin}" y="{height - options.margin + 8}">{_esc(footer_text)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def _layout_rows(layouts: list[MeasureLayout], options: RenderOptions) -> list[list[MeasureLayout]]:
    available = options.width - options.margin * 2
    if not layouts:
        return []
    rows: list[list[MeasureLayout]] = []
    row: list[MeasureLayout] = []
    used = 0.0
    for layout in layouts:
        layout.width = min(max(layout.width, options.min_measure_width), min(options.max_measure_width, available))
        if row and used + layout.width > available:
            _justify_row(row, available, is_last=False)
            rows.append(row)
            row = []
            used = 0.0
        row.append(layout)
        used += layout.width
    if row:
        _justify_row(row, available, is_last=True)
        rows.append(row)
    return rows


def _justify_row(row: list[MeasureLayout], available: float, *, is_last: bool) -> None:
    total = sum(measure.width for measure in row)
    if total <= 0:
        return
    limit = 1.06 if is_last else 1.18
    factor = min(limit, available / total)
    if factor <= 1.02:
        return
    for measure in row:
        measure.width *= factor


def _svg_header(options: RenderOptions, height: int, title: str, meta: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{options.width}" height="{height}" viewBox="0 0 {options.width} {height}">',
        "<defs>",
        "<style>",
        f"text {{ font-family: {options.font_family}; fill: #171717; letter-spacing: 0; }}",
        ".title { font-size: 40px; font-weight: 700; }",
        ".meta { font-size: 23px; }",
        ".note { font-size: 30px; font-weight: 650; }",
        ".accidental { font-size: 13px; font-weight: 400; }",
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
        ".accidental { font-size: 13px; font-weight: 400; }",
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


def _text_measure_layout(measure: str, number: int, beat_count: int, options: RenderOptions) -> MeasureLayout:
    tokens = measure.split() or ["0"]
    grouped = [[] for _ in range(max(1, beat_count))]
    cursor = Fraction(0, 1)
    for token in tokens:
        index = min(len(grouped) - 1, max(0, int(cursor)))
        grouped[index].append(RenderItem(token=token, duration=_token_duration(token)))
        cursor += _token_duration(token)
    return _measure_layout(measure, number, grouped, options)


def _score_measure_layout(measure, options: RenderOptions) -> MeasureLayout:
    fallback_beats = len(getattr(measure, "beats", [])) or 1
    beat_count = max(1, getattr(measure, "beats_per_measure", fallback_beats))
    grouped = _measure_render_items(measure, beat_count)
    while len(grouped) < beat_count:
        grouped.append([])
    return _measure_layout(
        measure,
        measure.display_number,
        grouped,
        options,
        errors=list(getattr(measure, "validation_errors", [])),
    )


def _first_ocr_measure_number(blocks: list[TextBlock]) -> int | None:
    candidates = [
        (index, block, int(block.text.strip()))
        for index, block in enumerate(blocks)
        if block.role == "measure_number" and block.text.strip().isdigit()
    ]
    if not candidates:
        return None
    candidates.sort(key=_text_block_reading_order)
    return candidates[0][2]


def _text_block_reading_order(candidate: tuple[int, TextBlock, int]) -> tuple[int, float, float, int]:
    index, block, _number = candidate
    if block.bbox is None:
        return (1, 0.0, 0.0, index)
    x1, y1, _x2, _y2 = block.bbox
    return (0, y1, x1, index)


def _measure_render_items(measure: Any, beat_count: int) -> list[list[RenderItem]]:
    beat_type = getattr(measure, "beat_type", 4)
    beat_duration = Fraction(4, beat_type)
    grouped: list[list[RenderItem]] = [[] for _ in range(max(1, beat_count))]

    events = list(getattr(measure, "events", []))
    if not events:
        measure_beats = list(getattr(measure, "beats", []))
        if measure_beats:
            for index, beat in enumerate(measure_beats[:beat_count]):
                grouped[index].extend(_event_to_item(event) for event in beat.events)
        return grouped

    cursor = Fraction(0, 1)
    for event in events:
        start = event.start if event.start is not None else cursor
        if event.kind == "rest" and event.duration > beat_duration:
            for beat_index, item in _split_rest_across_beats(event, start, beat_count, beat_duration):
                grouped[beat_index].append(item)
        else:
            beat_index = min(beat_count - 1, max(0, int(start / beat_duration)))
            grouped[beat_index].append(_event_to_item(event))
        cursor = start + event.duration
    return grouped


def _split_rest_across_beats(
    event: JianpuEvent,
    start: Fraction,
    beat_count: int,
    beat_duration: Fraction,
) -> list[tuple[int, RenderItem]]:
    pieces: list[tuple[int, RenderItem]] = []
    remaining = event.duration
    cursor = start
    while remaining > 0:
        beat_index = min(beat_count - 1, max(0, int(cursor / beat_duration)))
        beat_end = Fraction(beat_index + 1, 1) * beat_duration
        chunk = min(remaining, beat_end - cursor if beat_end > cursor else remaining)
        pieces.append(
            (
                beat_index,
                RenderItem(token="0" + _duration_suffix(chunk), duration=chunk, generated=event.generated, start=cursor),
            )
        )
        remaining -= chunk
        cursor += chunk
    return pieces


def _measure_layout(
    source: Any,
    number: str | int,
    grouped: list[list[RenderItem]],
    options: RenderOptions,
    errors: list[str] | None = None,
) -> MeasureLayout:
    beats = [
        BeatLayout(items=items, width=_beat_visual_width(items))
        for items in grouped
    ]
    natural = 42 + sum(beat.width for beat in beats) + max(0, len(beats) - 1) * options.beat_gap
    return MeasureLayout(
        source=source,
        number=number,
        beats=beats,
        width=max(options.min_measure_width, min(float(options.max_measure_width), natural)),
        errors=errors or [],
    )


def _beat_visual_width(items: list[RenderItem]) -> float:
    if not items:
        return 22.0
    return max(36.0, sum(_token_visual_width(item.token) for item in items) + max(0, len(items) - 1) * 9)


def _token_visual_width(token: str) -> float:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        parts = [part.strip() for part in token[1:-1].split("+") if part.strip()]
        extension = max((_parse_note(part).extension for part in parts), default=0)
        return 42 + extension * 16
    note = _parse_note(token)
    accidental_space = 12 if _split_accidental(note.display)[0] else 0
    return 30 + accidental_space + note.extension * 16 + (8 if note.dotted else 0)


def _render_measure(
    measure: MeasureLayout,
    x: float,
    y: int,
    width: float,
    options: RenderOptions,
    *,
    draw_start_bar: bool,
) -> list[str]:
    out = [f'<g class="measure" data-number="{_esc(str(measure.number))}" data-width="{width:.1f}">']
    if options.show_measure_numbers:
        out.append(f'<text class="measure-no" x="{x + 6:.1f}" y="{y - 62}">{_esc(str(measure.number))}</text>')
    if draw_start_bar:
        out.append(_bar_line(x, y))
    content_x = x + 26
    content_width = max(32.0, width - 56)
    natural_content = sum(beat.width for beat in measure.beats) + max(0, len(measure.beats) - 1) * options.beat_gap
    scale = content_width / natural_content if natural_content > 0 else 1.0
    beat_x = content_x
    measure_slots: list[tuple[RenderItem, float, float]] = []
    for beat_index, beat in enumerate(measure.beats):
        beat_width = beat.width * scale
        if options.show_beat_guides and beat_index > 0:
            out.append(
                f'<line class="beat-guide" x1="{beat_x:.1f}" y1="{y - 34}" '
                f'x2="{beat_x:.1f}" y2="{y + 52}"/>'
            )
        slots = _item_slots(beat.items, beat_x, beat_width)
        out.extend(_render_slot_items(slots, y))
        measure_slots.extend(slots)
        beat_x += beat_width + options.beat_gap * scale
    out.extend(_render_beams(measure_slots, y))
    out.extend(_render_spanners(measure_slots, y))
    out.extend(_render_measure_text_blocks(measure.source, x, y, width, measure_slots))
    if measure.errors:
        out.append(f'<text class="measure-no error" x="{x + 6:.1f}" y="{y + 80}">{_esc("; ".join(measure.errors))}</text>')
    out.append(_bar_line(x + width, y))
    out.append("</g>")
    return out


def _render_beat_items(items: list[RenderItem], x: float, width: float, y: int) -> list[str]:
    slots = _item_slots(items, x, width)
    return _render_slot_items(slots, y) + _render_beams(slots, y) + _render_spanners(slots, y)


def _item_slots(items: list[RenderItem], x: float, width: float) -> list[tuple[RenderItem, float, float]]:
    if not items:
        return []
    natural = sum(_token_visual_width(item.token) for item in items) + max(0, len(items) - 1) * 9
    scale = width / natural if natural > 0 else 1.0
    cursor = x
    slots: list[tuple[RenderItem, float, float]] = []
    for item in items:
        slot = _token_visual_width(item.token) * scale
        slots.append((item, cursor + slot / 2, slot))
        cursor += slot + 9 * scale
    return slots


def _render_slot_items(slots: list[tuple[RenderItem, float, float]], y: int) -> list[str]:
    out: list[str] = []
    beamed_ids = {id(item) for item, _, _ in slots if _beamable_slashes(item.token) > 0}
    for item, cx, slot in slots:
        out.extend(_render_item(item, cx, y, slot, suppress_duration=id(item) in beamed_ids))
    return out


def _render_measure_text_blocks(
    source: Any,
    x: float,
    y: int,
    width: float,
    slots: list[tuple[RenderItem, float, float]],
) -> list[str]:
    blocks = [
        block
        for block in getattr(source, "text_blocks", [])
        if block.text and block.role in {"expression", "other", "lyric"} and block.bbox is None
    ]
    out: list[str] = []
    seen: set[tuple[str, Fraction | None]] = set()
    used_lanes: dict[tuple[float, str], int] = {}
    for block in blocks:
        text = block.text.strip()
        start = getattr(block, "start", None)
        key = (text, start)
        if not text or key in seen:
            continue
        if _is_dynamic_text(text) and _slot_has_dynamic(slots, text, start):
            continue
        if block.role == "lyric" and _slot_has_lyric(slots, text, start):
            continue
        seen.add(key)
        class_name = "dynamic" if _is_dynamic_text(text) else "lyric"
        text_x = _measure_text_x(source, x, width, slots, start)
        placement = (getattr(block, "placement", None) or "below").lower()
        anchor = "middle" if start is not None else "start"
        base_y = y - 48 if placement == "above" else y + 62
        lane_key = (round(text_x, 1), placement)
        lane = used_lanes.get(lane_key, 0)
        used_lanes[lane_key] = lane + 1
        text_y = base_y - lane * 18 if placement == "above" else base_y + lane * 20
        out.append(f'<text class="{class_name}" x="{text_x:.1f}" y="{text_y:.1f}" text-anchor="{anchor}">{_esc(text)}</text>')
    return out


def _slot_has_dynamic(slots: list[tuple[RenderItem, float, float]], text: str, start: Fraction | None) -> bool:
    return any(item.dynamic == text and _same_start(item.start, start) for item, _, _ in slots)


def _slot_has_lyric(slots: list[tuple[RenderItem, float, float]], text: str, start: Fraction | None) -> bool:
    return any(item.lyric == text and _same_start(item.start, start) for item, _, _ in slots)


def _same_start(left: Fraction | None, right: Fraction | None) -> bool:
    if left is None or right is None:
        return left is right
    return left == right


def _measure_text_x(
    source: Any,
    x: float,
    width: float,
    slots: list[tuple[RenderItem, float, float]],
    start: Fraction | None,
) -> float:
    if start is not None:
        same_start = [(cx, slot_width) for item, cx, slot_width in slots if item.start == start]
        if same_start:
            return same_start[0][0]
        duration = getattr(source, "duration", None)
        if duration:
            ratio = max(0.0, min(1.0, float(start / duration)))
            return x + 26 + max(0.0, width - 56) * ratio
    return x + 28


def _render_positioned_text_blocks(
    blocks: list[TextBlock],
    width: int,
    height: int,
    *,
    include_measure_numbers: bool = True,
) -> list[str]:
    out: list[str] = []
    seen: set[tuple[str, tuple[float, float, float, float]]] = set()
    seen_texts: set[str] = set()
    unpositioned: list[TextBlock] = []
    for block in blocks:
        if not block.text:
            continue
        if block.role == "measure_number" and not include_measure_numbers:
            continue
        if block.bbox is None:
            unpositioned.append(block)
            continue
        x1, y1, x2, y2 = _scale_bbox(block.bbox, width, height)
        if x2 <= x1 or y2 <= y1:
            continue
        key = (block.text, (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)))
        if key in seen:
            continue
        seen.add(key)
        seen_texts.add(block.text.strip())

        font_size = max(8.0, min(34.0, (y2 - y1) * 0.78))
        class_name = "dynamic" if _is_dynamic_text(block.text) else "ocr-overlay"
        out.append(
            f'<text class="{class_name}" x="{x1:.1f}" y="{y2 - font_size * 0.16:.1f}" '
            f'font-size="{font_size:.1f}" text-anchor="start">{_esc(block.text)}</text>'
        )
    out.extend(_render_unpositioned_text_blocks(unpositioned, width, height, seen_texts))
    return out


def _render_unpositioned_text_blocks(
    blocks: list[TextBlock],
    width: int,
    height: int,
    seen_texts: set[str],
) -> list[str]:
    out: list[str] = []
    x = max(14.0, width * 0.035)
    y = max(28.0, height * 0.045)
    font_size = max(12.0, min(22.0, width / 70.0))
    line_gap = font_size * 1.35
    used: set[str] = set()
    for block in blocks:
        text = block.text.strip()
        if not text or text in seen_texts or text in used:
            continue
        used.add(text)
        class_name = "dynamic" if _is_dynamic_text(text) else "ocr-overlay"
        out.append(
            f'<text class="{class_name}" x="{x:.1f}" y="{y + (len(used) - 1) * line_gap:.1f}" '
            f'font-size="{font_size:.1f}" text-anchor="start">{_esc(text)}</text>'
        )
        if y + len(used) * line_gap > height - font_size:
            break
    return out


def _scale_bbox(bbox: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        return x1 * width, y1 * height, x2 * width, y2 * height
    return x1, y1, x2, y2


def _is_dynamic_text(text: str) -> bool:
    return text.strip() in {
        "p",
        "pp",
        "ppp",
        "pppp",
        "f",
        "ff",
        "fff",
        "ffff",
        "mp",
        "mf",
        "sf",
        "sfz",
        "sfp",
        "fp",
        "fz",
        "rfz",
    }


def _render_articulation(name: str, cx: float, y: int) -> list[str]:
    normalized = name.lower().replace("_", "-")
    if normalized == "fermata":
        return [
            f'<path class="articulation" d="M {cx - 10:.1f} {y - 42} Q {cx:.1f} {y - 54}, {cx + 10:.1f} {y - 42}"/>',
            f'<circle class="octave-dot" cx="{cx:.1f}" cy="{y - 43}" r="2.4"/>',
        ]
    if normalized in {"accent", "strong-accent"}:
        return [
            f'<path class="articulation" d="M {cx - 9:.1f} {y - 37} L {cx + 9:.1f} {y - 32} L {cx - 9:.1f} {y - 27}"/>'
        ]
    if normalized == "staccato":
        return [f'<circle class="octave-dot" cx="{cx:.1f}" cy="{y - 37}" r="2.5"/>']
    if normalized == "tenuto":
        return [f'<line class="articulation" x1="{cx - 8:.1f}" y1="{y - 36}" x2="{cx + 8:.1f}" y2="{y - 36}"/>']
    return [f'<text class="lyric" x="{cx:.1f}" y="{y - 38}" text-anchor="middle">{_esc(name)}</text>']


def _bar_line(x: float, y: int) -> str:
    return f'<line class="bar" x1="{x:.1f}" y1="{y - 50}" x2="{x:.1f}" y2="{y + 58}"/>'


def _render_beams(slots: list[tuple[RenderItem, float, float]], y: int) -> list[str]:
    out: list[str] = []
    for level in range(1, 4):
        run: list[tuple[RenderItem, float, float]] = []
        for slot in slots:
            item, _, _ = slot
            if _beamable_slashes(item.token) >= level:
                run.append(slot)
            else:
                out.extend(_render_beam_run(run, y, level))
                run = []
        out.extend(_render_beam_run(run, y, level))
    return out


def _render_beam_run(run: list[tuple[RenderItem, float, float]], y: int, level: int) -> list[str]:
    if not run:
        return []
    first_item, first_cx, _ = run[0]
    last_item, last_cx, _ = run[-1]
    start = first_cx - _beam_half_width(first_item.token)
    end = last_cx + _beam_half_width(last_item.token)
    beam_y = max(_beam_y(item.token, y, level) for item, _, _ in run)
    return [f'<line class="duration-line beam-line" x1="{start:.1f}" y1="{beam_y:.1f}" x2="{end:.1f}" y2="{beam_y:.1f}"/>']


def _beamable_slashes(token: str) -> int:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        notes = [_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()]
        if not notes:
            return 0
        return max((note.slashes for note in notes), default=0)
    note = _parse_note(token)
    return note.slashes


def _beam_half_width(token: str) -> float:
    token = token.strip().strip("()~")
    return 18.0 if token.startswith("[") and token.endswith("]") else 15.0


def _beam_y(token: str, y: int, level: int) -> float:
    return _duration_line_y(token, y, level)


def _event_to_item(event: JianpuEvent) -> RenderItem:
    token = "0" + _duration_suffix(event.duration) if event.kind == "rest" else _event_token(event)
    return RenderItem(
        token=token,
        duration=event.duration,
        generated=event.generated,
        start=event.start,
        lyric=event.lyric,
        tie_start=event.tie_start,
        tie_stop=event.tie_stop,
        slur_start=event.slur_start,
        slur_stop=event.slur_stop,
        dynamic=event.dynamic,
        articulation=event.articulation,
        articulations=list(getattr(event, "articulations", []) or ([event.articulation] if event.articulation else [])),
        ornaments=list(getattr(event, "ornaments", [])),
        technical=list(getattr(event, "technical", [])),
    )


def _events_to_beats(events: list[JianpuEvent], beat_count: int, beat_duration: Fraction):
    from ..domain.models import JianpuBeat

    beats = [JianpuBeat(index=index + 1, duration=beat_duration) for index in range(max(1, beat_count))]
    cursor = Fraction(0, 1)
    for event in events:
        start = event.start if event.start is not None else cursor
        index = min(len(beats) - 1, max(0, int(start / beat_duration)))
        beats[index].events.append(event)
        cursor = start + event.duration
    return beats


def _render_item(item: RenderItem, cx: float, y: int, slot_width: float, *, suppress_duration: bool = False) -> list[str]:
    out = _render_token(item.token, cx, y, generated=item.generated, suppress_duration=suppress_duration)
    if item.dynamic:
        out.append(f'<text class="dynamic" x="{cx:.1f}" y="{y + 58}" text-anchor="middle">{_esc(item.dynamic)}</text>')
    for index, mark in enumerate(_technique_marks(item)):
        out.append(
            f'<text class="technique-mark" x="{_technique_mark_x(item.token, cx):.1f}" '
            f'y="{_technique_mark_y(item.token, y) + index * 17:.1f}" text-anchor="start">{_esc(mark)}</text>'
        )
    upper_anchor_y = _upper_mark_anchor_y(item.token, y)
    articulations = item.articulations or ([item.articulation] if item.articulation else [])
    for index, articulation in enumerate(articulations[:4]):
        out.extend(_render_articulation(articulation, cx, upper_anchor_y - index * 12))
    visible_ornaments = [ornament for ornament in item.ornaments if _technique_mark(ornament) is None]
    for index, ornament in enumerate(visible_ornaments[:3]):
        out.append(
            f'<text class="ornament" x="{cx:.1f}" y="{upper_anchor_y - 46 - index * 14:.1f}" '
            f'text-anchor="middle">{_esc(_mark_display(ornament))}</text>'
        )
    visible_technical = [technical for technical in item.technical if _technique_mark(technical) is None]
    for index, technical in enumerate(visible_technical[:4]):
        out.append(
            f'<text class="technical" x="{cx:.1f}" y="{upper_anchor_y - 64 - index * 13:.1f}" '
            f'text-anchor="middle">{_esc(_mark_display(technical))}</text>'
        )
    if item.lyric:
        out.append(f'<text class="lyric" x="{cx:.1f}" y="{y + 48}" text-anchor="middle">{_esc(item.lyric)}</text>')
    return out


def _upper_mark_anchor_y(token: str, y: int) -> float:
    return _token_metrics(token, y)["top"] + 28.0


def _technique_marks(item: RenderItem) -> list[str]:
    marks: list[str] = []
    seen: set[str] = set()
    for name in [*item.ornaments, *item.technical]:
        mark = _technique_mark(name)
        if mark and mark not in seen:
            marks.append(mark)
            seen.add(mark)
    return marks


def _technique_mark(name: str) -> str | None:
    normalized = name.strip().lower().replace("_", "-").replace(" ", "-")
    return {
        "tremolo": "轮",
        "roll": "轮",
        "rolled": "轮",
        "lun": "轮",
        "lun-yin": "轮",
        "轮": "轮",
        "轮音": "轮",
    }.get(normalized)


def _technique_mark_x(token: str, cx: float) -> float:
    return cx + max(15.0, min(24.0, _token_visual_width(token) * 0.38))


def _technique_mark_y(token: str, y: int) -> float:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        notes = [_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()]
        if notes:
            top_y = y - (len(notes) - 1) * CHORD_GAP / 2
            return top_y + CHORD_GAP * (len(notes) - 1) + 20
    return y + 21


def _mark_display(name: str) -> str:
    normalized = name.strip().lower().replace("_", "-")
    return {
        "trill-mark": "tr",
        "mordent": "mord.",
        "inverted-mordent": "mord.",
        "turn": "turn",
        "delayed-turn": "turn",
        "inverted-turn": "turn",
        "tremolo": "轮",
        "up-bow": "up-bow",
        "down-bow": "down-bow",
        "harmonic": "harm.",
        "snap-pizzicato": "snap",
        "open-string": "open",
        "thumb-position": "thumb",
    }.get(normalized, name)


def _render_spanners(slots: list[tuple[RenderItem, float, float]], y: int) -> list[str]:
    out: list[str] = []
    open_tie: tuple[RenderItem, float, float] | None = None
    open_slur: tuple[RenderItem, float, float] | None = None
    for item, cx, slot_width in slots:
        current = (item, cx, slot_width)
        if item.tie_stop:
            if open_tie is None:
                out.append(_render_tie_arc(None, current, y))
            else:
                out.append(_render_tie_arc(open_tie, current, y))
                open_tie = None
        if item.slur_stop:
            if open_slur is None:
                out.append(_render_slur_arc(None, current, y))
            else:
                out.append(_render_slur_arc(open_slur, current, y))
                open_slur = None
        if item.tie_start:
            open_tie = current
        if item.slur_start:
            open_slur = current
    if open_tie is not None:
        out.append(_render_tie_arc(open_tie, None, y))
    if open_slur is not None:
        out.append(_render_slur_arc(open_slur, None, y))
    return out


def _render_tie_arc(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y)
    stop_metrics = _token_metrics(stop_item.token, y)
    arc_y = max(start_metrics["bottom"], stop_metrics["bottom"]) + 9
    if start is None:
        x1 = stop_cx - max(34.0, min(54.0, stop_slot + 12))
        x2 = stop_cx - 8
    elif stop is None:
        x1 = start_cx + 8
        x2 = start_cx + max(34.0, min(54.0, start_slot + 12))
    else:
        x1 = start_cx + 8
        x2 = stop_cx - 8
        if x2 - x1 < 26:
            center = (start_cx + stop_cx) / 2
            x1 = center - 18
            x2 = center + 18
    return _arc_between("tie", x1, x2, arc_y, max(7.0, min(12.0, (x2 - x1) / 10)))


def _render_slur_arc(
    start: tuple[RenderItem, float, float] | None,
    stop: tuple[RenderItem, float, float] | None,
    y: int,
) -> str:
    start_item, start_cx, start_slot = start if start is not None else stop  # type: ignore[misc]
    stop_item, stop_cx, stop_slot = stop if stop is not None else start  # type: ignore[misc]
    assert start_item is not None and stop_item is not None
    start_metrics = _token_metrics(start_item.token, y)
    stop_metrics = _token_metrics(stop_item.token, y)
    arc_y = min(start_metrics["top"], stop_metrics["top"]) - 22
    if start is None:
        x1 = stop_cx - max(46.0, min(72.0, stop_slot + 18))
        x2 = stop_cx + 5
    elif stop is None:
        x1 = start_cx - 5
        x2 = start_cx + max(46.0, min(72.0, start_slot + 18))
    else:
        x1 = start_cx - 5
        x2 = stop_cx + 5
        if x2 - x1 < 34:
            center = (start_cx + stop_cx) / 2
            x1 = center - 22
            x2 = center + 22
    return _arc_between("slur", x1, x2, arc_y, -max(14.0, min(26.0, (x2 - x1) / 8)))


def _arc(class_name: str, x: float, y: float, width: float, height: float, *, forward: bool) -> str:
    end_x = x + width if forward else x - width
    return _arc_between(class_name, x, end_x, y, height)


def _arc_between(class_name: str, x1: float, x2: float, y: float, height: float) -> str:
    width = x2 - x1
    control_y = y + height
    return (
        f'<path class="{class_name}" d="M {x1:.1f} {y:.1f} '
        f'C {x1 + width * 0.25:.1f} {control_y:.1f}, {x1 + width * 0.75:.1f} {control_y:.1f}, {x2:.1f} {y:.1f}"/>'
    )


def _event_token(event: JianpuEvent) -> str:
    suffix = _duration_suffix(event.duration)
    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    tokens = [_pitch_token(pitch) + suffix for pitch in pitches]
    if len(tokens) > 1:
        return "[" + "+".join(tokens) + "]"
    return tokens[0] if tokens else "?"


def _pitch_token(pitch: JianpuPitch) -> str:
    accidental = pitch.accidental_text
    if accidental is None:
        accidental = "#" if pitch.accidental > 0 else "b" if pitch.accidental < 0 else ""
    octave = "'" * max(0, pitch.octave) + "," * max(0, -pitch.octave)
    return f"{accidental}{pitch.degree}{octave}"


def _duration_suffix(duration: Fraction) -> str:
    if duration == Fraction(3, 2):
        return "."
    if duration == Fraction(3, 4):
        return "/."
    if duration == Fraction(3, 8):
        return "//."
    if duration >= 1:
        whole = int(duration)
        remain = duration - whole
        return "-" * max(0, whole - 1) + (_duration_suffix(remain) if remain else "")
    if duration == Fraction(1, 2):
        return "/"
    if duration == Fraction(1, 4):
        return "//"
    if duration == Fraction(1, 8):
        return "///"
    return ""


def _render_token(
    token: str,
    cx: float,
    y: int,
    *,
    generated: bool = False,
    suppress_duration: bool = False,
) -> list[str]:
    token = token.strip()
    slur_start = token.startswith("(")
    slur_stop = token.endswith(")")
    token = token.strip("()")
    tie_stop = token.startswith("~")
    tie_start = token.endswith("~")
    token = token.strip("~")
    if token.startswith("[") and token.endswith("]"):
        out = _render_chord(token, cx, y, generated=generated, suppress_duration=suppress_duration)
    else:
        out = _render_note_shape(_parse_note(token), cx, y, generated=generated, suppress_duration=suppress_duration)
    if tie_start:
        metrics = _token_metrics(token, y)
        out.append(_arc("tie", cx + 10, metrics["bottom"] + 5, max(34.0, min(68.0, _token_visual_width(token) + 16)), 9, forward=True))
    if tie_stop:
        metrics = _token_metrics(token, y)
        out.append(_arc("tie", cx - 52, metrics["bottom"] + 5, 42, 9, forward=True))
    if slur_start:
        metrics = _token_metrics(token, y)
        out.append(_arc("slur", cx - 10, metrics["top"] - 18, 74, -16, forward=True))
    if slur_stop:
        metrics = _token_metrics(token, y)
        out.append(_arc("slur", cx - 72, metrics["top"] - 18, 74, -16, forward=True))
    return out


def _render_chord(
    token: str,
    cx: float,
    y: int,
    *,
    generated: bool = False,
    suppress_duration: bool = False,
) -> list[str]:
    notes = sorted(
        (_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()),
        key=lambda note: note.rank,
        reverse=True,
    )
    if not notes:
        return []
    gap = CHORD_GAP
    top_y = y - (len(notes) - 1) * gap / 2
    out: list[str] = []
    for index, note in enumerate(notes):
        out.extend(_render_note_shape(note, cx, int(top_y + index * gap), generated=generated, suppress_duration=True))
    slashes = max(note.slashes for note in notes)
    dotted = any(note.dotted for note in notes)
    extension = max(note.extension for note in notes)
    underline_y = _duration_line_y(token, y, 1)
    if not suppress_duration:
        for line in range(min(3, slashes)):
            out.append(
                f'<line class="duration-line" x1="{cx - 18:.1f}" y1="{underline_y + line * 6:.1f}" '
                f'x2="{cx + 18:.1f}" y2="{underline_y + line * 6:.1f}"/>'
            )
    if dotted:
        out.append(f'<circle class="rhythm-dot" cx="{cx + 22:.1f}" cy="{top_y - 8:.1f}" r="3.0"/>')
    for mark in range(min(3, extension)):
        start = cx + 22 + mark * 16
        out.append(f'<line class="extension-line" x1="{start:.1f}" y1="{y - 9:.1f}" x2="{start + 28:.1f}" y2="{y - 9:.1f}"/>')
    return out


def _render_note_shape(
    note: NoteShape,
    cx: float,
    y: int,
    *,
    generated: bool = False,
    suppress_duration: bool = False,
) -> list[str]:
    note_class = "note generated" if generated else "note"
    accidental, body = _split_accidental(note.display)
    note_x = cx + (4 if accidental else 0)
    out: list[str] = []
    if accidental:
        out.append(f'<text class="accidental" x="{cx - 11.5:.1f}" y="{y - 6}" text-anchor="middle">{_esc(accidental)}</text>')
    out.append(f'<text class="{note_class}" x="{note_x:.1f}" y="{y}" text-anchor="middle">{_esc(body)}</text>')
    if not suppress_duration:
        for line in range(min(3, note.slashes)):
            line_y = _note_duration_line_y(note, y, line + 1)
            out.append(
                f'<line class="duration-line" x1="{cx - 13:.1f}" y1="{line_y:.1f}" '
                f'x2="{cx + 13:.1f}" y2="{line_y:.1f}"/>'
            )
    for dot in range(min(3, note.octave_up)):
        out.append(f'<circle class="octave-dot" cx="{cx:.1f}" cy="{y - 30 - dot * 9}" r="3.0"/>')
    for dot in range(min(3, note.octave_down)):
        out.append(f'<circle class="octave-dot" cx="{cx:.1f}" cy="{_low_octave_dot_y(y, dot):.1f}" r="3.0"/>')
    if note.dotted:
        out.append(f'<circle class="rhythm-dot" cx="{cx + 20:.1f}" cy="{y - 8}" r="3.0"/>')
    if not suppress_duration:
        for mark in range(min(3, note.extension)):
            start = cx + 20 + mark * 16
            out.append(f'<line class="extension-line" x1="{start:.1f}" y1="{y - 9:.1f}" x2="{start + 28:.1f}" y2="{y - 9:.1f}"/>')
    return out


def _split_accidental(display: str) -> tuple[str, str]:
    for token, symbol in (("bb", "bb"), ("x", "x"), ("n", "♮"), ("♮", "♮"), ("#", "#"), ("b", "b")):
        if display.startswith(token) and len(display) > len(token):
            return symbol, display[len(token):]
    return "", display


def _token_metrics(token: str, y: int) -> dict[str, float]:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        notes = [_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()]
        if not notes:
            return {"top": y - 28.0, "bottom": y + 14.0}
        gap = CHORD_GAP
        top_y = y - (len(notes) - 1) * gap / 2
        tops: list[float] = []
        bottoms: list[float] = []
        for index, note in enumerate(notes):
            note_y = int(top_y + index * gap)
            tops.append(_note_visual_top(note, note_y))
            bottoms.append(_note_visual_bottom(note, note_y, include_duration=False))
        bottom = max(bottoms)
        slashes = max((note.slashes for note in notes), default=0)
        extension = max((note.extension for note in notes), default=0)
        underline_y = top_y + gap * max(0, len(notes) - 1) + 18
        if slashes:
            bottom = max(bottom, underline_y + (min(3, slashes) - 1) * 6 + 4)
        if extension:
            bottom = max(bottom, underline_y + 21)
        return {"top": min(tops), "bottom": bottom}
    note = _parse_note(token)
    return {"top": _note_visual_top(note, y), "bottom": _note_visual_bottom(note, y, include_duration=True)}


def _note_visual_top(note: NoteShape, y: int) -> float:
    top = float(y - 28)
    if note.octave_up:
        top = min(top, y - 30 - (note.octave_up - 1) * 9 - 4)
    return top


def _note_visual_bottom(note: NoteShape, y: int, *, include_duration: bool) -> float:
    bottom = float(y + 14)
    if note.octave_down:
        bottom = max(bottom, _low_octave_dot_y(y, note.octave_down - 1) + 4)
    if include_duration and note.slashes:
        bottom = max(bottom, _note_duration_line_y(note, y, min(3, note.slashes)) + 4)
    if include_duration and note.extension:
        bottom = max(bottom, y + 34)
    return bottom


def _duration_line_y(token: str, y: int, level: int) -> float:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        notes = [_parse_note(part.strip()) for part in token[1:-1].split("+") if part.strip()]
        if not notes:
            return y + 10 + (level - 1) * 6
        top_y = y - (len(notes) - 1) * CHORD_GAP / 2
        base = top_y + CHORD_GAP * max(0, len(notes) - 1) + 18
        bottom = max(
            _note_visual_bottom(note, int(top_y + index * CHORD_GAP), include_duration=False)
            for index, note in enumerate(notes)
        )
        return max(base, bottom + 9) + (level - 1) * 6

    note = _parse_note(token)
    return _note_duration_line_y(note, y, level)


def _note_duration_line_y(note: NoteShape, y: int, level: int) -> float:
    base = y + 10
    if note.octave_down:
        base = max(base, _low_octave_dot_y(y, note.octave_down - 1) + 12)
    return base + (level - 1) * 6


def _low_octave_dot_y(y: int, index: int) -> float:
    return y + LOW_OCTAVE_DOT_OFFSET + index * OCTAVE_DOT_GAP


def _parse_note(token: str) -> NoteShape:
    token = token.strip().strip("()~")
    slashes = token.count("/")
    octave_up = token.count("'")
    octave_down = token.count(",")
    dotted = "." in token
    extension_match = re.search(r"(-*)$", token)
    extension = len(extension_match.group(1)) if extension_match else 0
    display = token.replace("'", "").replace(",", "").replace("/", "").replace(".", "")
    display = re.sub(r"((?:bb|[#bnx♮])?[0-7])[-]*$", r"\1", display)
    degree_match = re.search(r"([0-7])", display)
    degree = int(degree_match.group(1)) if degree_match else 0
    accidental = 0.2 if display.startswith("x") else 0.1 if "#" in display else -0.2 if display.startswith("bb") else -0.1 if "b" in display else 0
    return NoteShape(
        display=display,
        slashes=slashes,
        octave_up=octave_up,
        octave_down=octave_down,
        rank=(octave_up - octave_down) * 10 + degree + accidental,
        dotted=dotted,
        extension=extension,
    )


def _token_duration(token: str) -> Fraction:
    token = token.strip().strip("()~")
    if token.startswith("[") and token.endswith("]"):
        parts = [part.strip() for part in token[1:-1].split("+") if part.strip()]
        return min((_token_duration(part) for part in parts), default=Fraction(1, 1))
    extension_match = re.search(r"(-*)$", token)
    extension = len(extension_match.group(1)) if extension_match else 0
    token = token.rstrip("-")
    slashes = token.count("/")
    duration = Fraction(1, 2**slashes)
    if "." in token:
        duration += duration / 2
    return duration + extension


def _beats_from_time(time: str) -> int:
    try:
        return max(1, int(time.split("/", 1)[0]))
    except (ValueError, TypeError):
        return 4


def _split_header(text: str) -> tuple[str, str, str]:
    key = "C"
    time = "4/4"
    body_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("key="):
            key = stripped.split("=", 1)[1]
        elif stripped.startswith("time="):
            time = stripped.split("=", 1)[1]
        elif stripped:
            body_lines.append(stripped)
    return key, time, " ".join(body_lines)


def _extract_text_directives(text: str) -> tuple[str, list[TextBlock]]:
    lines: list[str] = []
    blocks: list[TextBlock] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@text "):
            block = _parse_text_directive(stripped)
            if block is not None:
                blocks.append(block)
            continue
        lines.append(line)
    return "\n".join(lines), blocks


def _parse_text_directive(line: str) -> TextBlock | None:
    parts = line.split(maxsplit=6)
    if len(parts) < 7:
        return None
    _mark, x1, y1, x2, y2, role, text = parts
    bbox = None
    if "-" not in {x1, y1, x2, y2}:
        try:
            bbox = (float(x1), float(y1), float(x2), float(y2))
        except ValueError:
            bbox = None
    if role not in {"title", "instrument", "lyric", "expression", "footer", "measure_number", "other"}:
        role = "other"
    return TextBlock(text=text.strip(), bbox=bbox, role=role)


def _split_measures(body: str) -> list[str]:
    measures = [measure.strip() for measure in re.split(r"\|", body) if measure.strip()]
    return measures or [body.strip()]


def _esc(value: str) -> str:
    return html.escape(value, quote=True)
