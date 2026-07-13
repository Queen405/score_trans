from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import json
import math
from pathlib import Path
from typing import Literal

from ....domain.performance_marks import get_performance_mark
from ....models.common.types import MeasureNumberMode
from ....models.score import Event, JianpuPitch, JianpuScore, Measure, TextBlock
from .scene import BBox, PublicationScene, SceneNode
from .fonts import font_registry
from .style import PublicationStyle
from .svg_backend import scene_to_svg


@dataclass(slots=True)
class MeasureRange:
    source_page_index: int
    start_measure_number: int | None
    end_measure_number: int | None


@dataclass(slots=True)
class PublicationPage:
    svg: str
    scene: PublicationScene
    measure_ranges: list[MeasureRange]
    note_index_start: int | None = None
    note_index_end: int | None = None


@dataclass(slots=True)
class _Cell:
    measures: list[Measure | None]
    width: float
    forced_system: bool = False
    forced_page: bool = False


@dataclass(slots=True)
class _System:
    cells: list[_Cell]
    widths: list[float]
    height: float
    force_page_before: bool = False


@dataclass(slots=True)
class _Anchor:
    x: float
    y: float
    bbox: BBox
    event: Event


@dataclass(slots=True)
class _OpenSpanners:
    tie: _Anchor | None = None
    slur: _Anchor | None = None
    slide: _Anchor | None = None


class PublicationRenderer:
    """Constraint-based, deterministic jianpu renderer.

    The implementation deliberately consumes ``JianpuScore`` directly.  No
    legacy token-layout or drawing helper is imported by this module.
    """

    engine_version = "publication-2"

    def __init__(self, style: PublicationStyle | None = None) -> None:
        self.style = style or PublicationStyle()

    def render_scores(
        self,
        scores: list[JianpuScore],
        *,
        title: str | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        page_width: float | None = None,
        page_height: float | None = None,
        page_text_blocks: dict[int, list[TextBlock]] | None = None,
    ) -> list[PublicationPage]:
        style = self._style_for_page(page_width, page_height)
        parts = _normalize_parts(scores)
        if not parts:
            parts = [[JianpuScore(title=title or "简谱")]]
        cells = _build_cells(parts, style)
        systems = _break_systems(cells, style, len(parts))
        pages = _paginate(systems, style)
        score0 = parts[0][0] if parts and parts[0] else JianpuScore()
        document_title = title or score0.title or "简谱"
        next_note_index = 0
        result: list[PublicationPage] = []
        for page_index, page_systems in enumerate(pages or [[]]):
            scene = PublicationScene(style.page_width, style.page_height, page_index)
            _page_chrome(scene, style, document_title, score0, page_index)
            note_start = next_note_index
            y = style.margin_top + (
                style.title_block_height if page_index == 0 else 54.0
            )
            page_ranges: list[MeasureRange] = []
            for system_index, system in enumerate(page_systems):
                next_note_index = self._draw_system(
                    scene,
                    style,
                    system,
                    parts,
                    y,
                    next_note_index,
                    show_measure_numbers=show_measure_numbers,
                    measure_number_mode=measure_number_mode,
                    first_system_on_page=system_index == 0,
                )
                _append_ranges(page_ranges, system.cells)
                y += system.height + style.system_gap
            for block in (page_text_blocks or {}).get(page_index, []):
                _draw_absolute_text(scene, block, style)
            note_end = next_note_index - 1 if next_note_index > note_start else None
            scene.note_index_start = note_start if note_end is not None else None
            scene.note_index_end = note_end
            result.append(
                PublicationPage(
                    svg=scene_to_svg(scene, style),
                    scene=scene,
                    measure_ranges=page_ranges,
                    note_index_start=scene.note_index_start,
                    note_index_end=scene.note_index_end,
                )
            )
        return result

    def write_pages(
        self,
        pages: list[PublicationPage],
        output_path: Path,
    ) -> list[Path]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for index, page in enumerate(pages):
            path = (
                output_path
                if len(pages) == 1
                else output_path.with_name(
                    f"{output_path.stem}_p{index + 1}{output_path.suffix or '.svg'}"
                )
            )
            path.write_text(page.svg, encoding="utf-8")
            map_path = path.with_suffix(".render-map.json")
            map_path.write_text(
                json.dumps(
                    page.scene.render_map_payload(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            paths.append(path)
        return paths

    def _style_for_page(
        self, page_width: float | None, page_height: float | None
    ) -> PublicationStyle:
        if page_width is None and page_height is None:
            return self.style
        from dataclasses import replace

        return replace(
            self.style,
            page_width=max(1.0, float(page_width or self.style.page_width)),
            page_height=max(1.0, float(page_height or self.style.page_height)),
        )

    def _draw_system(
        self,
        scene: PublicationScene,
        style: PublicationStyle,
        system: _System,
        parts: list[list[JianpuScore]],
        y: float,
        note_index: int,
        *,
        show_measure_numbers: bool,
        measure_number_mode: MeasureNumberMode,
        first_system_on_page: bool,
    ) -> int:
        x0 = style.margin_left
        part_count = max(1, len(parts))
        system_bottom = y + system.height - 12.0
        scene.add(_line("system-bracket", x0 - 12, y + 5, x0 - 12, system_bottom, 2.2))
        if part_count > 1:
            scene.add(
                SceneNode(
                    "path",
                    {
                        "class": "system-bracket",
                        "d": f"M {x0 - 12:g} {y + 5:g} q -13 7 0 15 M {x0 - 12:g} {system_bottom:g} q -13 -7 0 -15",
                        "stroke-width": 2.2,
                    },
                )
            )
        x = x0
        spanners = [_OpenSpanners() for _ in range(part_count)]
        for cell_index, (cell, width) in enumerate(
            zip(system.cells, system.widths, strict=True)
        ):
            for part_index in range(part_count):
                measure = (
                    cell.measures[part_index]
                    if part_index < len(cell.measures)
                    else None
                )
                staff_y = y + part_index * (style.base_staff_height + style.part_gap)
                if cell_index == 0 and part_count > 1:
                    part_name = _part_name(parts, part_index)
                    if part_name:
                        scene.add(
                            _text(
                                "part-name",
                                x - 18,
                                staff_y + 30,
                                part_name,
                                style.part_name_size,
                                anchor="end",
                            )
                        )
                if measure is None:
                    scene.add(
                        _line(
                            "measure",
                            x + width,
                            staff_y + 4,
                            x + width,
                            staff_y + style.base_staff_height - 8,
                            style.stroke_width,
                        )
                    )
                    continue
                draw_number = show_measure_numbers and (
                    measure_number_mode == "all"
                    or (measure_number_mode == "row_start" and cell_index == 0)
                )
                note_index = self._draw_measure(
                    scene,
                    style,
                    measure,
                    x,
                    staff_y,
                    width,
                    note_index,
                    spanners[part_index],
                    draw_number=draw_number,
                    draw_start_bar=cell_index == 0,
                )
            x += width
        for part_index, open_state in enumerate(spanners):
            staff_y = y + part_index * (style.base_staff_height + style.part_gap)
            _finish_spanners(scene, open_state, x0 + style.content_width, staff_y)
        return note_index

    def _draw_measure(
        self,
        scene: PublicationScene,
        style: PublicationStyle,
        measure: Measure,
        x: float,
        y: float,
        width: float,
        note_index: int,
        spanners: _OpenSpanners,
        *,
        draw_number: bool,
        draw_start_bar: bool,
    ) -> int:
        if draw_start_bar:
            scene.add(
                _line(
                    "measure",
                    x,
                    y + 4,
                    x,
                    y + style.base_staff_height - 8,
                    style.stroke_width,
                )
            )
        if draw_number:
            scene.add(
                _text(
                    "measure-no",
                    x + 7,
                    y - 9,
                    str(measure.display_number),
                    style.measure_number_size,
                )
            )
        attr = (
            f"1={measure.target_key}  {measure.beats_per_measure}/{measure.beat_type}"
        )
        scene.add(_text("measure-attribute", x + 8, y + 5, attr, style.annotation_size))
        if measure.ending_start:
            scene.add(_line("ending-line", x + 2, y - 22, x + width - 2, y - 22, 1.4))
            scene.add(
                _text(
                    "annotation",
                    x + 7,
                    y - 25,
                    str(measure.ending_start),
                    style.annotation_size,
                )
            )
        visual_events = _visual_events(measure)
        events = sorted(
            enumerate(visual_events),
            key=lambda item: (item[1].start or Fraction(item[0]), item[0]),
        )
        anchors: list[_Anchor] = []
        inner_left = x + 20.0
        inner_right = x + width - 20.0
        for event_pos, (_source_index, event) in enumerate(events):
            event_x = _event_x(
                event, event_pos, len(events), inner_left, inner_right, measure
            )
            anchor, consumed = _draw_event(
                scene, style, event, event_x, y + 43.0, note_index
            )
            anchors.append(anchor)
            if consumed:
                note_index += 1
            _route_spanners(scene, spanners, anchor, x, x + width)
        _draw_tuplets(scene, anchors, style)
        _draw_measure_text(scene, measure, x, y, width, style)
        if measure.repeat_start:
            scene.add(_circle("repeat-dot", x + 8, y + 37, 2.5))
            scene.add(_circle("repeat-dot", x + 8, y + 51, 2.5))
        if measure.repeat_end:
            scene.add(_circle("repeat-dot", x + width - 8, y + 37, 2.5))
            scene.add(_circle("repeat-dot", x + width - 8, y + 51, 2.5))
        scene.add(
            _line(
                "measure",
                x + width,
                y + 4,
                x + width,
                y + style.base_staff_height - 8,
                style.stroke_width,
            )
        )
        return note_index


def _normalize_parts(scores: list[JianpuScore]) -> list[list[JianpuScore]]:
    if not scores:
        return []
    multi = any(score.part_count > 1 or score.part_index > 0 for score in scores)
    if not multi:
        return [scores]
    by_part: dict[int, list[JianpuScore]] = {}
    for score in scores:
        by_part.setdefault(score.part_index, []).append(score)
    return [
        sorted(by_part[index], key=lambda score: score.page_index)
        for index in sorted(by_part)
    ]


def _flatten_measures(score_pages: list[JianpuScore]) -> list[Measure]:
    return [measure for score in score_pages for measure in score.measures]


def _build_cells(
    parts: list[list[JianpuScore]], style: PublicationStyle
) -> list[_Cell]:
    part_measures = [_flatten_measures(part) for part in parts]
    count = max((len(items) for items in part_measures), default=0)
    cells: list[_Cell] = []
    for index in range(count):
        measures = [
            items[index] if index < len(items) else None for items in part_measures
        ]
        present = [measure for measure in measures if measure is not None]
        width = max(
            (_intrinsic_measure_width(measure, style) for measure in present),
            default=style.minimum_measure_width,
        )
        cells.append(
            _Cell(
                measures=measures,
                width=width,
                forced_system=any(measure.new_system for measure in present),
                forced_page=any(measure.new_page for measure in present),
            )
        )
    return cells


def _intrinsic_measure_width(measure: Measure, style: PublicationStyle) -> float:
    width = 42.0
    for event in measure.events:
        chord = max(1, len(event.pitches))
        token_width = style.minimum_event_gap + (chord - 1) * 5.0
        if event.lyric:
            token_width = max(
                token_width, _text_width(event.lyric, style.lyric_size) + 10.0
            )
        marks = [*event.articulations, *event.ornaments, *event.technical]
        if marks:
            token_width = max(
                token_width,
                max(_text_width(mark, style.annotation_size) for mark in marks) + 8.0,
            )
        width += token_width
    return max(style.minimum_measure_width, min(style.content_width, width))


def _break_systems(
    cells: list[_Cell], style: PublicationStyle, part_count: int
) -> list[_System]:
    if not cells:
        return []
    systems: list[_System] = []
    start = 0
    while start < len(cells):
        forced_end = next(
            (
                index
                for index in range(start + 1, len(cells))
                if cells[index].forced_system or cells[index].forced_page
            ),
            len(cells),
        )
        end = _best_break(cells, start, forced_end, style.content_width)
        row = cells[start:end]
        natural = sum(cell.width for cell in row)
        is_last = end == len(cells)
        target = (
            natural
            if is_last
            and natural < style.content_width * style.last_line_fill_threshold
            else style.content_width
        )
        scale = target / natural if natural else 1.0
        widths = [cell.width * scale for cell in row]
        extra = _system_extra_height(row)
        height = (
            part_count * style.base_staff_height
            + max(0, part_count - 1) * style.part_gap
            + extra
        )
        systems.append(
            _System(
                row,
                widths,
                height,
                force_page_before=bool(row and row[0].forced_page),
            )
        )
        start = end
    return systems


def _best_break(cells: list[_Cell], start: int, limit: int, available: float) -> int:
    candidates: list[tuple[float, int]] = []
    width = 0.0
    for end in range(start + 1, limit + 1):
        width += cells[end - 1].width
        ratio = width / available
        if ratio > 1.18 and end > start + 1:
            break
        badness = abs(1.0 - ratio) ** 3 * 1000.0
        if end - start == 1 and end < len(cells):
            badness += 160.0
        candidates.append((badness, end))
    return min(candidates, default=(0.0, min(start + 1, len(cells))))[1]


def _paginate(systems: list[_System], style: PublicationStyle) -> list[list[_System]]:
    pages: list[list[_System]] = []
    current: list[_System] = []
    used = style.margin_top + style.title_block_height
    for system in systems:
        required = system.height + (style.system_gap if current else 0)
        if current and (
            used + required > style.content_bottom or system.force_page_before
        ):
            pages.append(current)
            current = []
            used = style.margin_top + 54.0
            required = system.height
        current.append(system)
        used += required
    if current or not pages:
        pages.append(current)
    return pages


def _system_extra_height(cells: list[_Cell]) -> float:
    events = [
        event
        for cell in cells
        for measure in cell.measures
        if measure
        for event in measure.events
    ]
    above = any(
        event.articulations or event.ornaments or event.technical or event.tuplet_count
        for event in events
    )
    below = any(event.lyric or event.dynamic for event in events)
    return (24.0 if above else 0.0) + (28.0 if below else 0.0)


def _page_chrome(
    scene: PublicationScene,
    style: PublicationStyle,
    title: str,
    score: JianpuScore,
    page_index: int,
) -> None:
    scene.add(
        SceneNode(
            "rect",
            {
                "class": "page-background",
                "x": 0,
                "y": 0,
                "width": style.page_width,
                "height": style.page_height,
            },
        )
    )
    if page_index == 0:
        scene.add(
            _text(
                "score-title",
                style.page_width / 2,
                style.margin_top + 26,
                title,
                style.title_size,
                anchor="middle",
            )
        )
        meta = f"1={score.target_key}    {score.beats}/{score.beat_type}"
        if score.tempo:
            meta += f"    ♩={score.tempo}"
        scene.add(
            _text(
                "score-meta",
                style.margin_left,
                style.margin_top + 78,
                meta,
                style.meta_size,
            )
        )
    else:
        scene.add(
            _text(
                "score-meta",
                style.margin_left,
                style.margin_top + 18,
                title,
                style.meta_size,
            )
        )
    scene.add(
        _text(
            "annotation page-number",
            style.page_width / 2,
            style.page_height - 24,
            str(page_index + 1),
            style.annotation_size,
            anchor="middle",
        )
    )


def _event_x(
    event: Event, position: int, count: int, left: float, right: float, measure: Measure
) -> float:
    if event.start is not None and measure.duration > 0:
        ratio = max(0.0, min(1.0, float(event.start / measure.duration)))
        return left + (right - left) * ratio
    return left + (right - left) * ((position + 0.5) / max(1, count))


def _draw_event(
    scene: PublicationScene,
    style: PublicationStyle,
    event: Event,
    x: float,
    y: float,
    note_index: int,
) -> tuple[_Anchor, bool]:
    pitched = event.kind == "note" and bool(event.pitches)
    token = event.source_token or _event_token(event)
    source_ids = list(
        dict.fromkeys(
            [
                *event.source_ids,
                *[pitch.source_id for pitch in event.pitches if pitch.source_id],
            ]
        )
    )
    bbox = BBox(x - 19, y - 29, 38, 76 if event.lyric else 51)
    attrs: dict[str, str | float | int] = {
        "class": "playback-note source-anchor" if pitched else "source-anchor",
        "data-note-token": token,
        "data-source-ids": " ".join(source_ids),
        "data-bbox": bbox.as_data(),
    }
    if source_ids:
        attrs["data-source-id"] = source_ids[0]
    if event.source_start_utf16 is not None:
        attrs["data-source-start-utf16"] = event.source_start_utf16
    if event.source_end_utf16 is not None:
        attrs["data-source-end-utf16"] = event.source_end_utf16
    if pitched:
        attrs["data-note-index"] = note_index
    marks = list(
        dict.fromkeys([*event.articulations, *event.ornaments, *event.technical])
    )
    if marks:
        attrs["data-mark"] = " ".join(marks)
    if event.slide_direction:
        attrs["data-slide-direction"] = event.slide_direction
    for role, role_ids in sorted(event.source_roles.items()):
        if role_ids:
            attrs[f"data-source-role-{role}"] = " ".join(role_ids)
    group = SceneNode("g", attrs)
    if event.kind == "rest" or not event.pitches:
        group.children.append(
            _text("note", x, y, "0", style.note_size, anchor="middle")
        )
    else:
        pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
        chord_gap = 25.0
        top = y - (len(pitches) - 1) * chord_gap / 2
        for pitch_index, pitch in enumerate(pitches):
            py = top + pitch_index * chord_gap
            _draw_pitch(group, style, pitch, x, py)
    _draw_duration(group, event, x, y, style)
    if event.lyric:
        group.children.append(
            _text("lyric", x, y + 44, event.lyric, style.lyric_size, anchor="middle")
        )
    if event.dynamic:
        group.children.append(
            _text(
                "dynamic",
                x,
                y + 63,
                event.dynamic,
                style.annotation_size,
                anchor="middle",
            )
        )
    _draw_marks(group, event, x, y, style)
    scene.add(group)
    scene.register_sources(source_ids, bbox)
    return _Anchor(x, y, bbox, event), pitched


def _draw_pitch(
    group: SceneNode, style: PublicationStyle, pitch: JianpuPitch, x: float, y: float
) -> None:
    accidental = _accidental_text(pitch)
    if accidental:
        group.children.append(
            _text(
                "accidental",
                x - 18,
                y,
                accidental,
                style.accidental_size,
                anchor="middle",
            )
        )
    group.children.append(
        _text(
            "note",
            x,
            y,
            str(max(0, min(7, pitch.degree))),
            style.note_size,
            anchor="middle",
        )
    )
    if pitch.octave:
        direction = -1 if pitch.octave > 0 else 1
        base_y = y - 21 if direction < 0 else y + 10
        for index in range(abs(pitch.octave)):
            group.children.append(
                _circle(
                    "octave-dot", x, base_y + direction * index * 7, 2.25, fill=True
                )
            )


def _draw_duration(
    group: SceneNode, event: Event, x: float, y: float, style: PublicationStyle
) -> None:
    duration = event.duration
    lines = 0
    unit = Fraction(1, 1)
    while duration > 0 and duration < unit and lines < 4:
        lines += 1
        unit /= 2
    for index in range(lines):
        ly = y + 13 + index * 6
        group.children.append(
            _line("duration-line beam-line", x - 12, ly, x + 12, ly, 1.8)
        )
    if duration > 1:
        extensions = max(0, int(math.ceil(float(duration))) - 1)
        for index in range(extensions):
            ex1 = x + 17 + index * 18
            group.children.append(
                _line("extension-line", ex1, y - 6, ex1 + 11, y - 6, 1.7)
            )
    for index in range(event.dotted):
        group.children.append(
            _circle("rhythm-dot", x + 17 + index * 7, y - 7, 2.1, fill=True)
        )


def _draw_marks(
    group: SceneNode, event: Event, x: float, y: float, style: PublicationStyle
) -> None:
    mark_ids = [*event.articulations, *event.ornaments, *event.technical]
    if event.articulation and event.articulation not in mark_ids:
        mark_ids.insert(0, event.articulation)
    top = y - 35
    for index, mark_id in enumerate(dict.fromkeys(mark_ids)):
        spec = get_performance_mark(mark_id)
        label = _mark_glyph(spec.renderer if spec else mark_id, mark_id)
        cls = "articulation" if index == 0 else "technique"
        if mark_id == "staccato":
            cls += " staccato"
        group.children.append(
            _text(
                cls, x, top - index * 16, label, style.annotation_size, anchor="middle"
            )
        )


def _route_spanners(
    scene: PublicationScene,
    state: _OpenSpanners,
    anchor: _Anchor,
    left: float,
    right: float,
) -> None:
    event = anchor.event
    for kind in ("tie", "slur", "slide"):
        start = bool(getattr(event, f"{kind}_start"))
        stop = bool(getattr(event, f"{kind}_stop"))
        current = getattr(state, kind)
        if stop and current is not None:
            scene.add(_spanner(kind, current, anchor))
            setattr(state, kind, None)
        if start:
            setattr(state, kind, anchor)


def _finish_spanners(
    scene: PublicationScene, state: _OpenSpanners, right: float, staff_y: float
) -> None:
    for kind in ("tie", "slur", "slide"):
        current = getattr(state, kind)
        if current is None:
            continue
        end = _Anchor(
            right - 3, current.y, BBox(right - 3, current.y, 1, 1), current.event
        )
        scene.add(_spanner(kind, current, end, continuation=True))


def _spanner(
    kind: str, start: _Anchor, end: _Anchor, continuation: bool = False
) -> SceneNode:
    if kind == "slide":
        delta = -13 if (start.event.slide_direction or "up") == "up" else 13
        d = f"M {start.x + 13:g} {start.y - 3:g} L {end.x - 13:g} {end.y + delta:g}"
    else:
        height = -17 if kind == "slur" else 13
        sx, ex = start.x + 10, end.x - 10
        mid = (sx + ex) / 2
        base = min(start.y, end.y) - 10 if height < 0 else max(start.y, end.y) + 11
        d = f"M {sx:g} {base:g} Q {mid:g} {base + height:g} {ex:g} {base:g}"
    attrs: dict[str, str | float | int] = {"class": kind, "d": d}
    if continuation:
        attrs["data-continuation"] = "end"
    return SceneNode("path", attrs)


def _draw_tuplets(
    scene: PublicationScene, anchors: list[_Anchor], style: PublicationStyle
) -> None:
    groups: dict[str, list[_Anchor]] = {}
    for anchor in anchors:
        event = anchor.event
        key = event.tuplet_id or (f"count-{id(event)}" if event.tuplet_count else "")
        if key:
            groups.setdefault(key, []).append(anchor)
    for group in groups.values():
        if not group:
            continue
        first, last = group[0], group[-1]
        count = first.event.tuplet_count or len(group)
        y = min(anchor.y for anchor in group) - 29
        scene.add(
            SceneNode(
                "path",
                {
                    "class": "tuplet-bracket",
                    "d": f"M {first.x - 11:g} {y + 5:g} V {y:g} H {last.x + 11:g} V {y + 5:g}",
                },
            )
        )
        scene.add(
            _text(
                "tuplet-number",
                (first.x + last.x) / 2,
                y + 1,
                str(count),
                style.annotation_size,
                anchor="middle",
            )
        )


def _draw_measure_text(
    scene: PublicationScene,
    measure: Measure,
    x: float,
    y: float,
    width: float,
    style: PublicationStyle,
) -> None:
    unpositioned = [
        block
        for block in measure.text_blocks
        if block.text and block.bbox is None and block.role != "measure_number"
    ]
    for index, block in enumerate(unpositioned):
        cls = "lyric" if block.role == "lyric" else "annotation"
        scene.add(
            _text(
                cls,
                x + width / 2,
                y + style.base_staff_height + 18 + index * 19,
                block.text,
                block.font_size or style.annotation_size,
                anchor="middle",
            )
        )


def _draw_absolute_text(
    scene: PublicationScene, block: TextBlock, style: PublicationStyle
) -> None:
    if not block.text or block.role == "measure_number":
        return
    if block.bbox:
        x1, y1, x2, y2 = block.bbox
        x, y = x1, y1 + (block.font_size or min(28.0, max(11.0, y2 - y1)))
    else:
        x, y = style.margin_left, style.margin_top + style.title_block_height - 15
    cls = "lyric" if block.role == "lyric" else "annotation"
    scene.add(_text(cls, x, y, block.text, block.font_size or style.annotation_size))


def _append_ranges(target: list[MeasureRange], cells: list[_Cell]) -> None:
    for cell in cells:
        for measure in cell.measures:
            if measure is None:
                continue
            page = measure.source_page_index or 0
            number = _measure_number(measure.display_number)
            existing = next(
                (item for item in target if item.source_page_index == page), None
            )
            if existing is None:
                target.append(MeasureRange(page, number, number))
            else:
                if number is not None:
                    existing.start_measure_number = min(
                        existing.start_measure_number or number, number
                    )
                    existing.end_measure_number = max(
                        existing.end_measure_number or number,
                        number + max(1, measure.repeat_count) - 1,
                    )
            break


def _measure_number(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _part_name(parts: list[list[JianpuScore]], index: int) -> str:
    return next(
        (score.part_name for score in parts[index] if score.part_name),
        f"声部 {index + 1}",
    )


def _event_token(event: Event) -> str:
    if event.kind == "rest" or not event.pitches:
        return "0"
    values = [str(pitch.degree) for pitch in event.pitches]
    return values[0] if len(values) == 1 else "[" + "+".join(values) + "]"


def _visual_events(measure: Measure) -> list[Event]:
    if len(measure.events) != 1:
        return list(measure.events)
    event = measure.events[0]
    if not event.generated or event.kind != "rest" or event.duration < measure.duration:
        return [event]
    beat = Fraction(4, max(1, measure.beat_type))
    count = max(1, int(measure.duration / beat))
    return [
        replace(
            event,
            duration=beat,
            start=beat * index,
            source_ids=list(event.source_ids) if index == 0 else [],
            source_roles=dict(event.source_roles) if index == 0 else {},
        )
        for index in range(count)
    ]


def _accidental_text(pitch: JianpuPitch) -> str:
    if pitch.accidental_text:
        return pitch.accidental_text
    value = pitch.accidental
    return {
        Fraction(2): "𝄪",
        Fraction(1): "♯",
        Fraction(1, 2): "↑",
        Fraction(-1, 2): "↓",
        Fraction(-1): "♭",
        Fraction(-2): "𝄫",
    }.get(value, "" if value == 0 else f"{float(value):+g}")


def _mark_glyph(renderer: str, fallback: str) -> str:
    return {
        "accent": ">",
        "tenuto": "—",
        "staccato": "●",
        "trill": "tr",
        "fermata": "𝄐",
        "down-bow": "Π",
        "up-bow": "∨",
        "natural-harmonic": "○",
        "artificial-harmonic": "◇",
        "pluck": "+",
        "open-string": "0",
        "inner-string": "内",
        "outer-string": "外",
        "breath-mark": "，",
        "arpeggio": "∿",
        "three-slash": "≋",
    }.get(renderer, fallback)


def _text_width(text: str, font_size: float) -> float:
    return font_registry().measure(text, font_size)


def _text(
    cls: str,
    x: float,
    y: float,
    value: str,
    size: float,
    *,
    anchor: Literal["start", "middle", "end"] = "start",
) -> SceneNode:
    return SceneNode(
        "text",
        {"class": cls, "x": x, "y": y, "font-size": size, "text-anchor": anchor},
        value,
    )


def _line(
    cls: str, x1: float, y1: float, x2: float, y2: float, width: float
) -> SceneNode:
    return SceneNode(
        "line",
        {"class": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "stroke-width": width},
    )


def _circle(
    cls: str, cx: float, cy: float, radius: float, fill: bool = False
) -> SceneNode:
    attrs: dict[str, str | float | int] = {
        "class": cls,
        "cx": cx,
        "cy": cy,
        "r": radius,
    }
    if fill:
        attrs["fill"] = "#171717"
    return SceneNode("circle", attrs)
