from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from typing import Literal

from ....config.settings import MIDI_TICKS_PER_BEAT
from ....domain.playback_timeline import (
    measure_boundaries,
    score_parts,
    to_tick,
    score_onset_groups,
    event_onsets,
)
from ....domain.jianpu_tokens import is_notatable_duration
from ....domain.voices import (
    LaneKey,
    events_are_polyphonic,
    group_event_lanes,
    lane_key,
)
from ....models.common.errors import RenderError
from ....models.common.types import MeasureNumberMode
from ....models.render.layout import PUBLICATION_ENGINE_VERSION
from ....models.score import (
    DEFAULT_TEMPO,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
    TupletSpan,
)
from .fonts import font_registry
from .geometry import (
    MarkLayout,
    _duration_extension_start,
    _dynamic_baseline,
    _event_attachment_bottom,
    _rhythm_line_count,
    mark_layouts,
    measure_event_ink,
    pitch_layouts,
)
from .mark_graphics import build_mark_graphic
from .qa import check_scene_geometry
from .scene import BBox, PublicationScene, SceneNode
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
    note_group_start: int | None = None
    note_group_end: int | None = None
    playback_start_tick: int | None = None
    playback_end_tick: int | None = None


@dataclass(slots=True)
class _Cell:
    index: int
    measures: list[Measure | None]
    width: float
    forced_system: bool = False
    forced_page: bool = False


@dataclass(slots=True)
class _PartLayout:
    offset: float = 0.0
    lanes: dict[LaneKey, float] = field(default_factory=dict)
    bar_top: float = 14.0
    bar_bottom: float = 69.0
    height: float = 92.0
    text_offset: float = 0.0


@dataclass(slots=True)
class _System:
    cells: list[_Cell]
    widths: list[float]
    height: float
    force_page_before: bool = False
    parts: list[_PartLayout] = field(default_factory=list)


@dataclass(slots=True)
class _Anchor:
    x: float
    y: float
    bbox: BBox
    event: Event
    continuation_start: bool = False


@dataclass(frozen=True, slots=True)
class SpanLayout:
    kind: str
    bbox: BBox
    source_ids: tuple[str, ...] = ()
    continuation: Literal["none", "start", "end"] = "none"
    allow_overlap: bool = False


@dataclass(frozen=True, slots=True)
class TextLayout:
    text: str
    bbox: BBox
    role: str
    lane_index: int
    font_size: float
    source_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _LaneSpanners:
    """单条声线的未闭合 spanner（tie/slur/slide）。"""

    tie: _Anchor | None = None
    slur: _Anchor | None = None
    slide: _Anchor | None = None


@dataclass(slots=True)
class _OpenSpanners:
    """每个声部一份；内部按声线（lane 序号）隔离，避免复调小节内跨声线串线。"""

    lanes: dict[LaneKey, _LaneSpanners] = field(default_factory=dict)
    continuations: set[tuple[LaneKey, str]] = field(default_factory=set)

    def lane(self, index: LaneKey) -> _LaneSpanners:
        return self.lanes.setdefault(index, _LaneSpanners())


class PublicationRenderer:
    """Constraint-based, deterministic jianpu renderer.

    The implementation deliberately consumes ``JianpuScore`` directly.  No
    legacy token-layout or drawing helper is imported by this module.
    """

    engine_version = PUBLICATION_ENGINE_VERSION

    def __init__(
        self,
        style: PublicationStyle | None = None,
        *,
        coordinate_scale: float = 1.0,
        layout_key: str = "",
    ) -> None:
        self.style = style or PublicationStyle()
        self.coordinate_scale = coordinate_scale
        self.layout_key = layout_key

    def render_scores(
        self,
        scores: list[JianpuScore],
        *,
        title: str | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        page_width: float | None = None,
        page_height: float | None = None,
        initial_measure_number: int | None = None,
        playback_group_offset: int = 0,
        playback_tick_offset: int = 0,
        show_title: bool = True,
        show_page_number: bool = True,
        page_index_offset: int = 0,
        fit_content_height: bool = False,
    ) -> list[PublicationPage]:
        style = self._style_for_page(page_width, page_height)
        parts = _normalize_parts(scores)
        if initial_measure_number is not None:
            _assign_display_measure_numbers(parts, initial_measure_number)
        if not parts:
            parts = [[JianpuScore(title=title)]]
        cells = _build_cells(parts, style)
        playback_groups = {
            cell_index: {
                onset: group + playback_group_offset for onset, group in groups.items()
            }
            for cell_index, groups in _playback_group_map(cells).items()
        }
        boundaries = measure_boundaries([cell.measures for cell in cells])
        systems = _break_systems(cells, style, len(parts))
        if fit_content_height:
            footer_height = style.page_height - _pagination_bottom(style)
            content_height = sum(system.height for system in systems)
            content_height += max(0, len(systems) - 1) * style.system_gap
            header_height = (
                style.title_block_height
                if show_title
                else style.continuation_header_height
            )
            style = replace(
                style,
                page_height=max(
                    style.page_height,
                    style.margin_top + header_height + content_height + footer_height,
                ),
            )
        pages = _paginate(systems, style, show_title=show_title)
        score0 = parts[0][0] if parts and parts[0] else JianpuScore()
        document_title = title or score0.title or ""
        next_note_index = 0
        document_spanners = [_OpenSpanners() for _ in range(max(1, len(parts)))]
        result: list[PublicationPage] = []
        for page_index, page_systems in enumerate(pages or [[]]):
            scene = PublicationScene(
                style.page_width * self.coordinate_scale,
                style.page_height * self.coordinate_scale,
                page_index,
                coordinate_scale=self.coordinate_scale,
                layout_key=self.layout_key,
            )
            _page_chrome(
                scene,
                style,
                document_title,
                score0,
                page_index + page_index_offset,
                show_title=show_title,
                show_page_number=show_page_number,
            )
            note_start = next_note_index
            y = style.margin_top + (
                style.title_block_height
                if page_index == 0 and show_title
                else style.continuation_header_height
            )
            page_ranges: list[MeasureRange] = []
            page_cells = [cell for system in page_systems for cell in system.cells]
            scene.playback_start_tick = (
                (
                    playback_tick_offset
                    + to_tick(boundaries[page_cells[0].index], MIDI_TICKS_PER_BEAT)
                )
                if page_cells
                else None
            )
            scene.playback_end_tick = (
                (
                    playback_tick_offset
                    + to_tick(boundaries[page_cells[-1].index + 1], MIDI_TICKS_PER_BEAT)
                )
                if page_cells
                else None
            )
            scene.playback_ppq = MIDI_TICKS_PER_BEAT
            page_groups = [
                group
                for system in page_systems
                for cell in system.cells
                for group in playback_groups.get(cell.index, {}).values()
            ]
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
                    spanners=document_spanners,
                    playback_groups=playback_groups,
                    playback_boundaries=boundaries,
                    playback_tick_offset=playback_tick_offset,
                )
                _append_ranges(page_ranges, system.cells)
                y += system.height + style.system_gap
            note_end = next_note_index - 1 if next_note_index > note_start else None
            scene.note_index_start = note_start if note_end is not None else None
            scene.note_index_end = note_end
            check_scene_geometry(scene, style)
            result.append(
                PublicationPage(
                    svg=scene_to_svg(scene, style),
                    scene=scene,
                    measure_ranges=page_ranges,
                    note_index_start=scene.note_index_start,
                    note_index_end=scene.note_index_end,
                    note_group_start=min(page_groups) if page_groups else None,
                    note_group_end=max(page_groups) if page_groups else None,
                    playback_start_tick=scene.playback_start_tick,
                    playback_end_tick=scene.playback_end_tick,
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
        spanners: list[_OpenSpanners],
        playback_groups: dict[int, dict[Fraction, int]] | None = None,
        playback_boundaries: list[Fraction] | None = None,
        playback_tick_offset: int = 0,
    ) -> int:
        x0 = style.margin_left
        part_count = max(1, len(parts))
        if part_count > 1:
            system_bottom = y + system.parts[-1].offset + system.parts[-1].bar_bottom
            scene.add(
                _line("system-bracket", x0 - 12, y + 14, x0 - 12, system_bottom, 2.2)
            )
            scene.add(
                SceneNode(
                    "path",
                    {
                        "class": "system-bracket",
                        "d": f"M {x0 - 12:g} {y + 14:g} q -13 7 0 15 M {x0 - 12:g} {system_bottom:g} q -13 -7 0 -15",
                        "stroke-width": 2.2,
                    },
                )
            )
        x = x0
        for part_index, state in enumerate(spanners):
            staff_y = y + system.parts[part_index].offset
            _start_spanner_continuations(
                state,
                x0,
                staff_y + style.event_baseline,
                lane_offsets=system.parts[part_index].lanes,
            )
        for cell_index, (cell, width) in enumerate(
            zip(system.cells, system.widths, strict=True)
        ):
            shared_positions = _shared_cell_positions(cell.measures, x, width, style)
            cell_groups = playback_groups.get(cell.index) if playback_groups else None
            for part_index in range(part_count):
                measure = (
                    cell.measures[part_index]
                    if part_index < len(cell.measures)
                    else None
                )
                staff_y = y + system.parts[part_index].offset
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
                            staff_y + system.parts[part_index].bar_top,
                            x + width,
                            staff_y + system.parts[part_index].bar_bottom,
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
                    draw_attribute=_measure_attributes_changed(
                        parts, part_index, cell.index
                    ),
                    draw_tempo=part_index == 0
                    and _measure_tempo_changed(parts, part_index, cell.index),
                    draw_terminal=(
                        cell.index == len(_flatten_measures(parts[part_index])) - 1
                    ),
                    shared_positions=shared_positions,
                    note_groups=cell_groups,
                    playback_start=(
                        playback_boundaries[cell.index]
                        if playback_boundaries
                        else Fraction(0)
                    ),
                    playback_tick_offset=playback_tick_offset,
                    part_index=part_index,
                    part_layout=system.parts[part_index],
                )
            x += width
        for part_index, open_state in enumerate(spanners):
            staff_y = y + system.parts[part_index].offset
            _finish_spanners(scene, open_state, x, staff_y, style)
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
        draw_attribute: bool,
        draw_tempo: bool,
        draw_terminal: bool,
        shared_positions: dict[Fraction, float] | None = None,
        note_groups: dict[Fraction, int] | None = None,
        playback_start: Fraction = Fraction(0),
        playback_tick_offset: int = 0,
        part_index: int = 0,
        part_layout: _PartLayout | None = None,
    ) -> int:
        visual_events = _visual_events(measure)
        lane_groups = _measure_render_lanes(visual_events)
        if part_layout is not None and part_layout.lanes:
            lane_groups = [
                [event for event in visual_events if lane_key(event) == key]
                for key in part_layout.lanes
            ]
        bar_top, bar_bottom = _measure_bar_offsets(measure, style)
        if part_layout is not None:
            bar_top, bar_bottom = part_layout.bar_top, part_layout.bar_bottom
        if draw_start_bar or measure.repeat_start:
            _draw_barline(
                scene,
                x,
                y + bar_top,
                y + bar_bottom,
                style,
                kind="repeat-start" if measure.repeat_start else "normal",
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
        repeat_count = max(1, int(getattr(measure, "repeat_count", 1) or 1))
        if repeat_count > 1:
            scene.add(
                _text(
                    "repeat-count",
                    x + width - 7,
                    y - 9,
                    f"*{repeat_count}",
                    style.measure_number_size,
                    anchor="end",
                )
            )
        if draw_tempo and measure.tempo is not None:
            label = f"♩={measure.tempo}"
            left = x + 7
            if draw_number:
                left += (
                    font_registry().measure(
                        str(measure.display_number), style.measure_number_size
                    )
                    + 6
                )
            right = x + width - 7
            if repeat_count > 1:
                right -= (
                    font_registry().measure(
                        f"*{repeat_count}", style.measure_number_size
                    )
                    + 6
                )
            scene.add(
                _text(
                    "tempo-mark",
                    (left + right) / 2,
                    y - 9,
                    label,
                    style.annotation_size,
                    anchor="middle",
                )
            )
        if draw_attribute:
            attr = (
                f"1={measure.target_key}  "
                f"{measure.beats_per_measure}/{measure.beat_type}"
            )
            scene.add(
                _text("measure-attribute", x + 8, y + 9, attr, style.annotation_size)
            )
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
        anchors: list[_Anchor] = []
        # Attributes sit in the upper-left annotation band and must not consume
        # horizontal event slots; otherwise a key/meter change shifts the bar.
        #
        # Clip limits mark how far derived marks (rhythm lines, extension lines)
        # may reach — into the gutter but never past the barline. Event centres
        # additionally keep a rhythm-line side extent away from those limits,
        # because the shared line is no longer part of per-event ink.
        clip_left = x + style.barline_gutter
        clip_right = x + width - style.barline_gutter
        beat_boundaries = (
            _beat_boundaries(measure) if style.break_beams_at_beat else None
        )
        if lane_groups is None:
            events = sorted(
                enumerate(visual_events),
                key=lambda item: (
                    item[1].start if item[1].start is not None else Fraction(item[0]),
                    item[0],
                ),
            )
            ordered_events = [event for _source_index, event in events]
            pad_left, pad_right = _rhythm_edge_padding(ordered_events, style)
            event_positions = _event_positions(
                ordered_events,
                clip_left + pad_left,
                clip_right - pad_right,
                measure,
                style,
            )
            if shared_positions:
                event_positions = [
                    shared_positions.get(event.start or Fraction(0), position)
                    for event, position in zip(
                        ordered_events, event_positions, strict=True
                    )
                ]
            note_index = _draw_event_group(
                scene,
                style,
                events,
                event_positions,
                y + style.event_baseline,
                note_index,
                clip_right=clip_right,
                note_groups=note_groups,
                playback_start=playback_start,
                playback_tick_offset=playback_tick_offset,
                part_index=part_index,
                spanners=spanners,
                lane=None,
                measure_left=x,
                measure_right=x + width,
                subtext_offset=0.0,
                anchors=anchors,
            )
        else:
            # 复调小节：每条声线独立成行，共享小节线；跨声线用 union onset
            # 对齐（与多声部 shared_positions 同一机制），同一时刻各声线同 x。
            lane_probes: list[Measure | None] = [
                _lane_probe(measure, lane_events) for lane_events in lane_groups
            ]
            lane_positions = shared_positions or _shared_cell_positions(
                lane_probes, x, width, style
            )
            lane_offsets = part_layout.lanes if part_layout is not None else {}
            lyric_offset = part_layout.text_offset if part_layout is not None else 0.0
            for lane_rank, lane_events in enumerate(lane_groups):
                if not lane_events:
                    continue
                key = lane_key(lane_events[0])
                baseline_offset = lane_offsets.get(key, lane_rank * style.voice_row_gap)
                lane_anchors: list[_Anchor] = []
                events = sorted(
                    enumerate(lane_events),
                    key=lambda item: (
                        item[1].start
                        if item[1].start is not None
                        else Fraction(item[0]),
                        item[0],
                    ),
                )
                ordered_events = [event for _source_index, event in events]
                pad_left, pad_right = _rhythm_edge_padding(ordered_events, style)
                event_positions = _event_positions(
                    ordered_events,
                    clip_left + pad_left,
                    clip_right - pad_right,
                    measure,
                    style,
                )
                if lane_positions:
                    event_positions = [
                        lane_positions.get(event.start or Fraction(0), position)
                        for event, position in zip(
                            ordered_events, event_positions, strict=True
                        )
                    ]
                note_index = _draw_event_group(
                    scene,
                    style,
                    events,
                    event_positions,
                    y + style.event_baseline + baseline_offset,
                    note_index,
                    clip_right=clip_right,
                    note_groups=note_groups,
                    playback_start=playback_start,
                    playback_tick_offset=playback_tick_offset,
                    part_index=part_index,
                    spanners=spanners,
                    lane=key,
                    measure_left=x,
                    measure_right=x + width,
                    # lane 1 的歌词/力度移到所有声线之下，避免与 lane 2 数字重叠
                    subtext_offset=max(0.0, lyric_offset - baseline_offset),
                    anchors=lane_anchors,
                )
                _draw_rhythm_lines(
                    scene, lane_anchors, clip_left, clip_right, style, beat_boundaries
                )
                _draw_tuplets(scene, lane_anchors, style)
                anchors.extend(lane_anchors)
        if lane_groups is None:
            _draw_rhythm_lines(
                scene, anchors, clip_left, clip_right, style, beat_boundaries
            )
            _draw_tuplets(scene, anchors, style)
        text_offset = part_layout.text_offset if part_layout is not None else 0.0
        _draw_measure_text(scene, measure, x, y + text_offset, width, style)
        repeat_center = (bar_top + bar_bottom) / 2
        if measure.repeat_start:
            scene.add(
                _circle("repeat-dot", x + 12, y + repeat_center - 7, 2.3, fill=True)
            )
            scene.add(
                _circle("repeat-dot", x + 12, y + repeat_center + 7, 2.3, fill=True)
            )
        if measure.repeat_end:
            scene.add(
                _circle(
                    "repeat-dot", x + width - 12, y + repeat_center - 7, 2.3, fill=True
                )
            )
            scene.add(
                _circle(
                    "repeat-dot", x + width - 12, y + repeat_center + 7, 2.3, fill=True
                )
            )
        _draw_barline(
            scene,
            x + width,
            y + bar_top,
            y + bar_bottom,
            style,
            kind=(
                "repeat-end"
                if measure.repeat_end
                else ("terminal" if draw_terminal else "normal")
            ),
        )
        return note_index


def _measure_render_lanes(visual_events: list[Event]) -> list[list[Event]] | None:
    """真复调小节按声线分组视觉事件（含 extension 槽位），否则返回 None。

    仅在同一 staff 上不同 voice 时间重叠时拆分；分组顺序与
    ``group_event_lanes`` 一致（voice 数字升序、staff 次之）。
    """
    # Extension slots still occupy musical time. Include them in overlap
    # detection; otherwise a later entry loses the sustained voice beside it.
    occupancy = [
        replace(event, kind="rest") if event.kind == "extension" else event
        for event in visual_events
    ]
    if not events_are_polyphonic(occupancy):
        return None
    lanes = group_event_lanes(occupancy)
    if len(lanes) < 2:
        return None
    grouped: dict[LaneKey, list[Event]] = {key: [] for key, _events in lanes}
    for event in visual_events:
        if event.kind == "rest" and event.hidden and event.tuplet_id is None:
            continue
        key = lane_key(event)
        if key in grouped:
            grouped[key].append(event)
    return [grouped[key] for key, _events in lanes]


def _lane_probe(measure: Measure, events: list[Event]) -> Measure:
    return Measure(
        source_number=measure.source_number,
        duration=measure.duration,
        events=events,
        beats_per_measure=measure.beats_per_measure,
        beat_type=measure.beat_type,
    )


def _draw_event_group(
    scene: PublicationScene,
    style: PublicationStyle,
    events: list[tuple[int, Event]],
    event_positions: list[float],
    baseline_y: float,
    note_index: int,
    *,
    clip_right: float,
    note_groups: dict[Fraction, int] | None,
    playback_start: Fraction,
    playback_tick_offset: int,
    part_index: int,
    spanners: _OpenSpanners,
    lane: LaneKey | None,
    measure_left: float,
    measure_right: float,
    subtext_offset: float,
    anchors: list[_Anchor],
) -> int:
    """按给定水平位置绘制一组事件（单线小节的全组，或复调小节的一条声线）。"""
    for event_pos, (_source_index, event) in enumerate(events):
        event_x = event_positions[event_pos]
        note_group = (
            note_groups.get(event.start or Fraction(0)) if note_groups else None
        )
        anchor, consumed = _draw_event(
            scene,
            style,
            event,
            event_x,
            baseline_y,
            note_index,
            right_limit=clip_right,
            note_group=note_group,
            playback_tick=playback_tick_offset
            + to_tick(
                playback_start + (event.start or Fraction(0)), MIDI_TICKS_PER_BEAT
            ),
            part_index=part_index,
            subtext_offset=subtext_offset,
        )
        anchors.append(anchor)
        if consumed:
            note_index += 1
        _route_spanners(
            scene,
            spanners,
            anchor,
            measure_left,
            measure_right,
            style,
            lane=lane if lane is not None else lane_key(event),
        )
    return note_index


def _measure_bar_offsets(
    measure: Measure, style: PublicationStyle
) -> tuple[float, float]:
    top = 14.0
    bottom = 66.0
    for event in measure.events:
        rows = pitch_layouts(event, style)
        notation_top = min((row.note_box.top for row in rows), default=-25.0)
        notation_bottom = max((row.note_box.bottom for row in rows), default=9.0)
        for row in rows:
            if row.accidental_box is not None:
                notation_top = min(notation_top, row.accidental_box.top)
            for box in row.octave_boxes:
                notation_top = min(notation_top, box.top)
                notation_bottom = max(notation_bottom, box.bottom)
        top = min(top, style.event_baseline + notation_top - 3.0)
        bottom = max(bottom, style.event_baseline + notation_bottom + 4.0)
        rhythm_lines = _rhythm_line_count(event)
        if rhythm_lines:
            base = style.event_baseline + _rhythm_line_offset(event, style)
            bottom = max(
                bottom,
                base + (rhythm_lines - 1) * style.rhythm_line_level_step + 2.0,
            )
    return top, bottom


def _draw_barline(
    scene: PublicationScene,
    x: float,
    top: float,
    bottom: float,
    style: PublicationStyle,
    *,
    kind: Literal["normal", "terminal", "repeat-start", "repeat-end"],
) -> None:
    if kind == "normal":
        scene.add(_line("measure", x, top, x, bottom, style.stroke_width))
        return
    if kind == "terminal":
        scene.add(_line("measure terminal-barline", x - 6, top, x - 6, bottom, 1.4))
        scene.add(_line("measure terminal-barline", x, top, x, bottom, 4.2))
        return
    if kind == "repeat-start":
        scene.add(_line("measure repeat-barline", x, top, x, bottom, 4.0))
        scene.add(_line("measure repeat-barline", x + 6, top, x + 6, bottom, 1.4))
        return
    scene.add(_line("measure repeat-barline", x - 6, top, x - 6, bottom, 1.4))
    scene.add(_line("measure repeat-barline", x, top, x, bottom, 4.0))


def _normalize_parts(scores: list[JianpuScore]) -> list[list[JianpuScore]]:
    return score_parts(scores)


def _assign_display_measure_numbers(
    parts: list[list[JianpuScore]], initial_measure_number: int
) -> None:
    current = max(1, int(initial_measure_number))
    if len(parts) <= 1:
        for score in parts[0] if parts else []:
            current = _assign_score_measure_numbers(score, current)
        return
    for page_index in range(max(len(part_pages) for part_pages in parts)):
        page_span = 0
        for part_pages in parts:
            if page_index >= len(part_pages):
                continue
            page_span = max(
                page_span,
                sum(
                    max(1, int(getattr(measure, "repeat_count", 1) or 1))
                    for measure in part_pages[page_index].measures
                ),
            )
            _assign_score_measure_numbers(part_pages[page_index], current)
        current += page_span


def _assign_score_measure_numbers(score: JianpuScore, start: int) -> int:
    current = start
    for measure in score.measures:
        measure.display_number = current
        for block in measure.text_blocks:
            if block.role == "measure_number":
                block.text = str(current)
                block.measure_number = current
        current += max(1, int(getattr(measure, "repeat_count", 1) or 1))
    return current


def _flatten_measures(score_pages: list[JianpuScore]) -> list[Measure]:
    return [measure for score in score_pages for measure in score.measures]


def _measure_attributes_changed(
    parts: list[list[JianpuScore]], part_index: int, measure_index: int
) -> bool:
    if measure_index <= 0 or part_index >= len(parts):
        return False
    measures = _flatten_measures(parts[part_index])
    if measure_index >= len(measures):
        return False
    previous = measures[measure_index - 1]
    current = measures[measure_index]
    return (
        current.target_key != previous.target_key
        or current.beats_per_measure != previous.beats_per_measure
        or current.beat_type != previous.beat_type
    )


def _measure_tempo_changed(
    parts: list[list[JianpuScore]], part_index: int, measure_index: int
) -> bool:
    if measure_index <= 0 or part_index >= len(parts):
        return False
    measures = _flatten_measures(parts[part_index])
    if measure_index >= len(measures):
        return False
    return measures[measure_index].tempo != measures[measure_index - 1].tempo


def _tempo_header_min_width(measure: Measure, style: PublicationStyle) -> float:
    labels = [
        str(measure.display_number),
        f"♩={measure.tempo}",
    ]
    if measure.repeat_count > 1:
        labels.append(f"*{measure.repeat_count}")
    widths = [font_registry().measure(label, style.annotation_size) for label in labels]
    return 14.0 + sum(widths) + 6.0 * (len(widths) - 1)


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
        widths = [_intrinsic_measure_width(measure, style) for measure in present]
        if len(present) > 1:
            shared_width = _shared_intrinsic_measure_width(present, style)
            if shared_width is not None:
                widths.append(shared_width)
        if (
            measures
            and measures[0] is not None
            and _measure_tempo_changed(parts, 0, index)
        ):
            widths[0] = max(widths[0], _tempo_header_min_width(measures[0], style))
        width = max(widths, default=style.minimum_measure_width)
        cells.append(
            _Cell(
                index=index,
                measures=measures,
                width=width,
                forced_system=any(measure.new_system for measure in present),
                forced_page=any(measure.new_page for measure in present),
            )
        )
    return cells


def _intrinsic_measure_width(measure: Measure, style: PublicationStyle) -> float:
    if not measure.events:
        return style.minimum_measure_width
    visual = _visual_events(measure)
    if not visual:
        return style.minimum_measure_width
    # 复调小节按声线分组后，宽度需求是各声线 union onset 的布局需求，
    # 与多声部共享宽度同一机制（任一单线布局都不够装下并行的两组事件）。
    lane_groups = _measure_render_lanes(visual)
    if lane_groups is not None:
        shared = _shared_intrinsic_measure_width(
            [_lane_probe(measure, lane_events) for lane_events in lane_groups],
            style,
        )
        if shared is not None:
            return shared
    events = sorted(
        visual,
        key=lambda event: event.start if event.start is not None else Fraction(0),
    )
    extents = [_event_visual_extents(event, style) for event in events]
    if not extents:
        return style.minimum_measure_width
    gaps = _preferred_event_gaps(events, extents, style, _beat_boundaries(measure))
    pad_left, pad_right = _rhythm_edge_padding(events, style)
    width = (
        style.measure_side_padding
        + (extents[-1][1] + pad_right)
        - (extents[0][0] - pad_left)
        + sum(gaps)
    )
    return max(style.minimum_measure_width, min(style.content_width, width))


def _preferred_event_gaps(
    events: list[Event],
    extents: list[tuple[float, float, float, float]],
    style: PublicationStyle,
    boundaries: list[Fraction] | None,
) -> list[float]:
    """Return the per-gap widths a measure asks for, short-note control applied.

    The scale may compress past the duration spring but not past the ink
    collision and beat-boundary floors, or the cell would be too narrow to
    hold its own content.
    """
    preferred = _minimum_event_gaps(
        events,
        extents,
        _common_shortest_duration(events),
        style,
        boundaries,
    )
    scale = style.short_note_gap_scale
    if scale == 1.0:
        return list(preferred)
    # Symmetric on purpose: lowering the control has to narrow the cell so
    # _break_systems fits more measures per line. Applying it only above 1.0
    # left the cell unchanged and turned the saved room into dead space at
    # the bar edges, which is why the control looked inert.
    gaps = [
        gap * scale if _is_short_note_pair(events[index], events[index + 1]) else gap
        for index, gap in enumerate(preferred)
    ]
    floors = _hard_event_gaps(events, extents, style, boundaries)
    return [max(floor, gap) for floor, gap in zip(floors, gaps, strict=True)]


def _spacing_lanes(
    measures: list[Measure | None],
) -> list[tuple[Measure, list[Event]]]:
    result: list[tuple[Measure, list[Event]]] = []
    for measure in measures:
        if measure is None:
            continue
        visual = _visual_events(measure)
        groups = _measure_render_lanes(visual) or [visual]
        for events in groups:
            ordered = sorted(events, key=lambda event: event.start or Fraction(0))
            # A simultaneous event adds ink constraints, not a new time slot.
            # Separate coincident events into independent spacing sequences so
            # no onset dictionary can overwrite another event's requirement.
            sequences: list[list[Event]] = []
            for event in ordered:
                sequence = next(
                    (items for items in sequences if items[-1].start != event.start),
                    None,
                )
                if sequence is None:
                    sequence = []
                    sequences.append(sequence)
                sequence.append(event)
            result.extend((measure, items) for items in sequences)
    return result


def _shared_intrinsic_measure_width(
    measures: list[Measure], style: PublicationStyle
) -> float | None:
    """Return the cell width the shared multi-part onset layout asks for.

    Laying out the union of all parts' onsets can need more room than any
    single part (one part dense at the start, another dense at the end), so
    the cell width must consider the union requirement rather than only the
    per-part maxima, or the draw-time justification would have to compress
    below the parts' minimum gaps.
    """
    per_part = _spacing_lanes(measures)
    if len(per_part) < 2:
        return None
    union = sorted(
        {
            event.start or Fraction(0)
            for _measure, events in per_part
            for event in events
        }
    )
    if len(union) < 2:
        return None
    rel_maps: list[dict[Fraction, float]] = []
    left_outer = 0.0
    right_outer = 0.0
    for measure, events in per_part:
        extents = [_event_visual_extents(event, style) for event in events]
        gaps = _preferred_event_gaps(events, extents, style, _beat_boundaries(measure))
        relative = [0.0]
        for gap in gaps:
            relative.append(relative[-1] + gap)
        rel_maps.append(
            {
                event.start or Fraction(0): offset
                for event, offset in zip(events, relative, strict=True)
            }
        )
        pad_left, pad_right = _rhythm_edge_padding(events, style)
        left_outer = min(left_outer, extents[0][0] - pad_left)
        right_outer = max(right_outer, extents[-1][1] + pad_right)
    total = 0.0
    for start, end in zip(union, union[1:]):
        total += _union_interval_shares(rel_maps, start, end)
    width = style.measure_side_padding + (right_outer - left_outer) + total
    return max(style.minimum_measure_width, min(style.content_width, width))


def _playback_group_map(cells: list[_Cell]) -> dict[int, dict[Fraction, int]]:
    """Stable original-score onset IDs shared with MIDI source-position markers.

    Repeated performances refer back to these IDs; they do not add SVG groups.
    """
    measures = [cell.measures for cell in cells]
    boundaries = measure_boundaries(measures)
    groups = score_onset_groups(measures)
    return {
        cell.index: {
            start: groups[boundaries[index] + start]
            for measure in cell.measures
            if measure is not None
            for start, event in event_onsets(measure)
            if event.kind == "note" and event.pitches
        }
        for index, cell in enumerate(cells)
    }


def _shared_cell_positions(
    measures: list[Measure | None], x: float, width: float, style: PublicationStyle
) -> dict[Fraction, float]:
    """Return one x coordinate per onset shared by every part in a cell.

    An empty mapping means "fall back to the per-part layout".  Single-part
    cells keep the per-part spring layout untouched.  For multi-part cells the
    union of all onsets is laid out once: each inter-onset gap is the maximum
    share any part needs across that interval, so every part's minimum spacing
    is preserved (per-part gaps telescope over the union intervals) while
    identical onsets share one coordinate across all parts.
    """
    per_part = _spacing_lanes(measures)
    if len(per_part) < 2:
        return {}
    union = sorted(
        {
            event.start or Fraction(0)
            for _measure, events in per_part
            for event in events
        }
    )
    if not union:
        return {}
    clip_left = x + style.barline_gutter
    clip_right = x + width - style.barline_gutter
    part_maps: list[dict[Fraction, float]] = []
    pad_right_max = 0.0
    for measure, events in per_part:
        pad_left, pad_right = _rhythm_edge_padding(events, style)
        pad_right_max = max(pad_right_max, pad_right)
        positions = _event_positions(
            events,
            clip_left + pad_left,
            clip_right - pad_right,
            measure,
            style,
        )
        part_maps.append(
            {
                event.start or Fraction(0): position
                for event, position in zip(events, positions, strict=True)
            }
        )
    start0 = max(
        (positions[union[0]] for positions in part_maps if union[0] in positions),
        default=clip_left,
    )
    if len(union) == 1:
        return {union[0]: start0}
    intervals = list(zip(union, union[1:]))
    required = [
        _union_interval_shares(part_maps, start, end) for start, end in intervals
    ]
    total = sum(required)
    available = max(0.0, clip_right - pad_right_max - start0)
    if total <= 0.0:
        gaps = [0.0 for _ in required]
    elif total <= available:
        extra = available - total
        weights = [float(end - start) for start, end in intervals]
        weight_sum = sum(weights) or 1.0
        gaps = [
            need + extra * weight / weight_sum
            for need, weight in zip(required, weights, strict=True)
        ]
    else:
        # The cell is narrower than the union requirement (its width comes
        # from the widest single part).  Compress uniformly; per-part order
        # and monotone spacing are preserved because requirements shrink
        # proportionally rather than dropping to zero selectively.
        scale = available / total
        gaps = [need * scale for need in required]
    positions = {union[0]: start0}
    for (start, end), gap in zip(intervals, gaps, strict=True):
        positions[end] = positions[start] + gap
    return positions


def _union_interval_shares(
    part_maps: list[dict[Fraction, float]], start: Fraction, end: Fraction
) -> float:
    """Return the maximum x span any part needs across the onset interval.

    A part whose own onsets bracket the interval contributes its proportional
    share of the bracketed span; summing the shares over the union intervals
    inside a part's own gap reproduces that gap, so per-part minimum spacing
    survives the max() aggregation.
    """
    need = 0.0
    for positions in part_maps:
        prev = max((onset for onset in positions if onset <= start), default=None)
        nxt = min((onset for onset in positions if onset >= end), default=None)
        if prev is None or nxt is None or nxt <= prev:
            continue
        span = positions[nxt] - positions[prev]
        need = max(need, span * float((end - start) / (nxt - prev)))
    return need


def _common_shortest_duration(events: list[Event]) -> Fraction:
    durations = [event.duration for event in events if event.duration > 0]
    if not durations:
        return Fraction(1, 2)
    counts = Counter(durations)
    return min(min(counts, key=lambda value: (-counts[value], value)), Fraction(1, 2))


def _duration_spring(
    duration: Fraction,
    common_shortest: Fraction,
    style: PublicationStyle,
) -> float:
    if duration <= 0 or common_shortest <= 0:
        return style.minimum_event_gap
    ratio = float(duration / common_shortest)
    if ratio >= 1.0:
        return style.minimum_event_gap + style.spacing_increment * math.log2(ratio)
    return max(16.0, style.minimum_event_gap * ratio)


def _same_tuplet_group(previous: Event, current: Event) -> bool:
    return bool(previous.tuplet_id and previous.tuplet_id == current.tuplet_id)


def _is_short_note_pair(previous: Event, current: Event) -> bool:
    return (
        previous.kind == "note"
        and current.kind == "note"
        and previous.duration <= Fraction(1, 2)
        and current.duration <= Fraction(1, 2)
    )


def _rhythm_edge_padding(
    events: list[Event], style: PublicationStyle
) -> tuple[float, float]:
    """Return the side room the outer events need for their rhythm lines.

    ``measure_event_ink`` no longer reserves the rhythm line's side extent as
    per-event horizontal ink, so the outermost event centres must stay far
    enough inside the measure for the shared line to be drawn without being
    clipped. Positioning uses these paddings; the clip limits stay at the
    barline gutter so the line may still reach into it.
    """
    if not events:
        return 0.0, 0.0
    extent = style.rhythm_line_side_extent
    left = extent if _rhythm_line_count(events[0]) > 0 else 0.0
    right = extent if _rhythm_line_count(events[-1]) > 0 else 0.0
    return left, right


def _boundary_extra_gap(
    previous: Event, current: Event, crosses_beat: bool, style: PublicationStyle
) -> float:
    extra = 0.0
    if _is_tuplet(previous) or _is_tuplet(current):
        extra = style.tuplet_boundary_gap
    if crosses_beat:
        extra = max(extra, style.beat_boundary_gap)
    return extra


def _hard_event_gaps(
    events: list[Event],
    extents: list[tuple[float, float, float, float]],
    style: PublicationStyle,
    beat_boundaries: list[Fraction] | None = None,
) -> list[float]:
    """Return the gaps that no compaction may cross.

    Unlike :func:`_minimum_event_gaps` this omits the duration spring, which is
    a spacing *preference* rather than a physical constraint: the short-note
    control has to be able to compress past it. What remains is the ink
    collision floor plus the tuplet and beat-boundary reservations, so tightening
    the control can never overlap glyphs nor flatten the beat division.
    """
    subdivided = _subdivided_beat_crossings(events, beat_boundaries)
    gaps: list[float] = []
    for index in range(1, len(events)):
        previous = events[index - 1]
        current = events[index]
        collision_gap = (
            extents[index - 1][1] - extents[index][0] + style.event_clearance
        )
        if _same_tuplet_group(previous, current):
            gaps.append(collision_gap)
            continue
        gaps.append(
            collision_gap
            + _boundary_extra_gap(previous, current, subdivided[index - 1], style)
        )
    return gaps


def _minimum_event_gaps(
    events: list[Event],
    extents: list[tuple[float, float, float, float]],
    common_shortest: Fraction,
    style: PublicationStyle,
    beat_boundaries: list[Fraction] | None = None,
) -> list[float]:
    subdivided = _subdivided_beat_crossings(events, beat_boundaries)
    gaps: list[float] = []
    for index in range(1, len(events)):
        previous = events[index - 1]
        current = events[index]
        previous_right = extents[index - 1][1]
        current_left = extents[index][0]
        collision_gap = previous_right - current_left + style.event_clearance
        previous_start = previous.start if previous.start is not None else Fraction(0)
        current_start = (
            current.start
            if current.start is not None
            else previous_start + previous.duration
        )
        time_gap = _duration_spring(
            current_start - previous_start,
            common_shortest,
            style,
        )
        if _same_tuplet_group(previous, current):
            time_gap = max(18.0, style.minimum_event_gap * 0.72)
            gaps.append(max(collision_gap, time_gap))
            continue
        base_gap = max(collision_gap, time_gap)
        gaps.append(
            base_gap
            + _boundary_extra_gap(previous, current, subdivided[index - 1], style)
        )
    return gaps


def _beat_boundaries(measure: Measure) -> list[Fraction]:
    """Return sorted beat-start positions plus the final end position.

    Prefers ``measure.beats`` (authoritative parser output); falls back to a
    simple-meter subdivision derived from ``beat_type`` and ``duration`` for raw
    measures constructed without going through the parser.
    """
    if measure.beats:
        starts = [beat.start for beat in measure.beats]
        last = measure.beats[-1]
        return [*starts, last.start + last.duration]
    beat_unit = Fraction(4, max(1, measure.beat_type))
    if measure.duration > 0:
        count = max(1, round(measure.duration / beat_unit))
    else:
        count = max(1, measure.beats_per_measure)
    return [beat_unit * index for index in range(count + 1)]


def _subdivided_beat_crossings(
    events: list[Event],
    beat_boundaries: list[Fraction] | None,
) -> list[bool]:
    """For each gap between consecutive events, report whether it crosses a beat
    boundary whose preceding beat holds more than one event.

    Events are assumed to be ordered by start (as produced by the renderer's
    sort). The returned list has ``len(events) - 1`` entries.
    """
    if not beat_boundaries or len(beat_boundaries) < 2 or len(events) < 2:
        return [False] * max(0, len(events) - 1)

    interior = beat_boundaries[1:-1]
    if not interior:
        return [False] * (len(events) - 1)

    starts: list[Fraction] = []
    cursor = Fraction(0)
    for event in events:
        start = event.start if event.start is not None else cursor
        starts.append(start)
        cursor = start + event.duration

    def beat_index(start: Fraction) -> int:
        index = 0
        for boundary in interior:
            if start >= boundary:
                index += 1
            else:
                break
        return index

    beat_of = [beat_index(start) for start in starts]
    events_per_beat: dict[int, int] = {}
    for index in beat_of:
        events_per_beat[index] = events_per_beat.get(index, 0) + 1

    crossings: list[bool] = []
    for gap_index in range(1, len(events)):
        previous_beat = beat_of[gap_index - 1]
        current_beat = beat_of[gap_index]
        crossings.append(
            current_beat > previous_beat and events_per_beat[previous_beat] > 1
        )
    return crossings


def _tuplet_run_count(events: list[Event]) -> int:
    count = 0
    previous_id: str | None = None
    for event in events:
        current_id = event.tuplet_id
        if current_id and current_id != previous_id:
            count += 1
        previous_id = current_id
    return count


def _event_visual_extents(
    event: Event, style: PublicationStyle
) -> tuple[float, float, float, float]:
    box = measure_event_ink(event, style)
    return box.left, box.right, box.top, box.bottom


def _break_systems(
    cells: list[_Cell], style: PublicationStyle, part_count: int
) -> list[_System]:
    if not cells:
        return []
    systems: list[_System] = []
    part_keys: list[list[LaneKey]] = []
    for index in range(part_count):
        events = [
            event
            for cell in cells
            if index < len(cell.measures) and cell.measures[index] is not None
            for event in _visual_events(cell.measures[index])
        ]
        polyphonic = any(
            index < len(cell.measures)
            and cell.measures[index] is not None
            and _measure_render_lanes(_visual_events(cell.measures[index])) is not None
            for cell in cells
        )
        part_keys.append(
            [key for key, _ in group_event_lanes(events)] if polyphonic else []
        )
    start = 0
    for end in _optimal_system_ends(cells, style):
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
        layouts = _system_part_layouts(row, widths, style, part_keys)
        height = layouts[-1].offset + layouts[-1].height if layouts else 0.0
        systems.append(
            _System(
                row,
                widths,
                height,
                force_page_before=bool(row and row[0].forced_page),
                parts=layouts,
            )
        )
        start = end
    return systems


def _system_part_layouts(
    cells: list[_Cell],
    widths: list[float],
    style: PublicationStyle,
    part_keys: list[list[LaneKey]],
) -> list[_PartLayout]:
    layouts: list[_PartLayout] = []
    cursor = 0.0
    for index, keys in enumerate(part_keys):
        measures = [
            (cell.measures[index], width)
            for cell, width in zip(cells, widths, strict=True)
            if index < len(cell.measures) and cell.measures[index] is not None
        ]
        visual = [event for measure, _ in measures for event in _visual_events(measure)]
        offsets: dict[LaneKey, float] = {}
        previous_bottom = 0.0
        baseline = 0.0
        for rank, key in enumerate(keys):
            events = [event for event in visual if lane_key(event) == key]
            boxes = [
                measure_event_ink(replace(event, lyric=None, dynamic=None), style)
                for event in events
            ]
            top = min((box.top for box in boxes), default=-29.0)
            bottom = max((box.bottom for box in boxes), default=14.0)
            if any(event.slur_start or event.slur_stop for event in events):
                top -= max(30.0, style.slur_height) + style.spanner_base_clearance
            if any(event.tie_start or event.tie_stop for event in events):
                bottom += style.tie_below_clearance + max(
                    4.0, min(12.0, style.tie_height)
                )
            rhythm = [
                event for event in events if _rhythm_line_count(event) or event.beams
            ]
            if rhythm:
                levels = max(
                    max(
                        _rhythm_line_count(event),
                        max(
                            (int(b.number) for b in event.beams if b.number.isdigit()),
                            default=0,
                        ),
                    )
                    for event in rhythm
                )
                bottom = max(
                    bottom,
                    max(_rhythm_line_offset(event, style) for event in rhythm)
                    + max(0, levels - 1) * style.rhythm_line_level_step
                    + style.stroke_width,
                )
            if any(_is_tuplet(event) for event in events):
                top -= style.tuplet_bracket_offset + style.annotation_size
            if rank:
                baseline += max(
                    style.voice_row_gap, previous_bottom - top + style.voice_clearance
                )
            offsets[key] = baseline
            previous_bottom = bottom
        text_offset = max(offsets.values(), default=0.0)
        bar_top, bar_bottom = 14.0, 69.0
        for measure, _ in measures:
            groups = (
                [
                    [e for e in _visual_events(measure) if lane_key(e) == key]
                    for key in keys
                ]
                if keys
                else [_visual_events(measure)]
            )
            for events in groups:
                if not events:
                    continue
                offset = offsets.get(lane_key(events[0]), 0.0)
                top, bottom = _measure_bar_offsets(_lane_probe(measure, events), style)
                bar_top = min(bar_top, top + offset)
                bar_bottom = max(bar_bottom, bottom + offset)
        probes = [
            _Cell(cell.index, [cell.measures[index]], width)
            for cell, width in zip(cells, widths, strict=True)
            if index < len(cell.measures)
        ]
        extra = _system_extra_height(probes, style)
        height = style.base_staff_height + extra
        if offsets:
            depth = max(
                (
                    style.event_baseline
                    + offsets.get(lane_key(e), 0.0)
                    + measure_event_ink(
                        replace(e, lyric=None, lyrics={}, dynamic=None), style
                    ).bottom
                    for e in visual
                ),
                default=bar_bottom,
            )
            for e in visual:
                if e.dynamic:
                    depth = max(
                        depth,
                        style.event_baseline
                        + text_offset
                        + measure_event_ink(replace(e, lyric=None, lyrics={}), style).bottom,
                    )
            for measure, width in measures:
                for text in _measure_text_layout(
                    measure, 0.0, width, text_offset, style
                ):
                    depth = max(depth, text.bbox.y + text.bbox.height)
            height = max(
                height,
                depth + style.system_bottom_reserve,
                bar_bottom + style.system_bottom_reserve,
            )
        top_ink = min(
            (
                style.event_baseline
                + offsets.get(lane_key(e), 0.0)
                + measure_event_ink(e, style).top
                for e in visual
            ),
            default=14.0,
        )
        if index:
            cursor += max(0.0, -top_ink)
        layouts.append(
            _PartLayout(cursor, offsets, bar_top, bar_bottom, height, text_offset)
        )
        cursor += height + style.part_gap
    return layouts


def _boundary_penalties(cells: list[_Cell], style: PublicationStyle) -> list[float]:
    """Track spans through every measure, matching the drawing stop/start order."""
    penalties = [0.0]
    active: dict[tuple[int, LaneKey, str], bool] = {}
    for cell in cells:
        penalty = 0.0
        for part, measure in enumerate(cell.measures):
            if measure is None:
                continue
            last_lyric = None
            for event in measure.events:
                for kind in ("slur", "tie", "slide"):
                    key = (part, lane_key(event), kind)
                    if getattr(event, f"{kind}_stop"):
                        active[key] = False
                    if getattr(event, f"{kind}_start"):
                        active[key] = True
                if event.lyric:
                    last_lyric = event.lyric
            if last_lyric and not last_lyric.rstrip().endswith(
                tuple("。，；！？.,;!?")
            ):
                penalty += style.lyric_break_penalty
        penalty += sum(
            style.slur_break_penalty if kind == "slur" else style.tie_break_penalty
            for (_, _lane, kind), opened in active.items()
            if opened
        )
        penalties.append(penalty)
    return penalties


def _optimal_system_ends(cells: list[_Cell], style: PublicationStyle) -> list[int]:
    """Shortest path over feasible rows; width bounds keep candidates local."""
    count = len(cells)
    penalties = _boundary_penalties(cells, style)
    costs = [math.inf] * (count + 1)
    following = [count] * count
    costs[count] = 0.0
    for start in range(count - 1, -1, -1):
        width = 0.0
        for end in range(start + 1, count + 1):
            if end > start + 1 and (
                cells[end - 1].forced_system or cells[end - 1].forced_page
            ):
                break
            width += cells[end - 1].width
            ratio = width / style.content_width
            if ratio > style.max_system_overflow_ratio and end > start + 1:
                break
            ragged_last = end == count and ratio < style.last_line_fill_threshold
            badness = 0.0 if ragged_last else abs(1.0 - ratio) ** 3 * 1000.0
            if end - start == 1 and count > 1 and ratio < 0.6:
                badness += style.singleton_system_penalty
            forced = end < count and (
                cells[end].forced_system or cells[end].forced_page
            )
            if end < count and not forced:
                badness += penalties[end]
            total = badness + costs[end]
            if total < costs[start]:
                costs[start] = total
                following[start] = end
    ends = []
    start = 0
    while start < count:
        start = following[start]
        ends.append(start)
    return ends


def _pagination_bottom(style: PublicationStyle) -> float:
    # Page number baseline is shared with _page_chrome. Use actual ink height,
    # not the baseline, and never spend the tolerance inside the footer band.
    _, ink_top, _, _ = font_registry().ink_bounds("0123456789", style.annotation_size)
    footer_top = style.page_height - 24 + ink_top - style.footer_clearance
    return min(
        style.content_bottom + max(0.0, style.pagination_bottom_allowance),
        style.page_height - style.footer_reserved,
        footer_top,
    )


def _paginate(
    systems: list[_System], style: PublicationStyle, *, show_title: bool = True
) -> list[list[_System]]:
    pages: list[list[_System]] = []
    current: list[_System] = []
    used = style.margin_top + (
        style.title_block_height if show_title else style.continuation_header_height
    )
    content_bottom = _pagination_bottom(style)
    for system in systems:
        required = system.height + (style.system_gap if current else 0)
        if current and (used + required > content_bottom or system.force_page_before):
            pages.append(current)
            current = []
            used = style.margin_top + style.continuation_header_height
            required = system.height
        if used + required > content_bottom + 1e-6:
            raise RenderError("单个谱表系统超出页面可用高度，请缩小谱面或增大页面")
        current.append(system)
        used += required
    if current or not pages:
        pages.append(current)
    return pages


def _system_extra_height(cells: list[_Cell], style: PublicationStyle) -> float:
    top_extra = 0.0
    bottom_extra = 0.0
    needs_top = False
    needs_bottom = False
    for cell in cells:
        for measure in cell.measures:
            if measure is None:
                continue
            # 复调小节的附加声线占用垂直空间，系统高度按小节级 lane 数加高
            visual = _visual_events(measure)
            lane_groups = _measure_render_lanes(visual)
            if lane_groups is not None:
                bottom_extra = max(
                    bottom_extra,
                    (len(lane_groups) - 1) * style.voice_row_gap,
                )
                needs_bottom = True
            for event in measure.events:
                box = measure_event_ink(event, style)
                top_extra = max(top_extra, max(0.0, -box.top - 29.0))
                bottom_extra = max(bottom_extra, max(0.0, box.bottom - 64.0))
                needs_top = needs_top or bool(
                    event.articulations
                    or event.ornaments
                    or event.technical
                    or event.tuplet_count
                    or event.tuplet_spans
                    or any(pitch.octave > 0 for pitch in event.pitches)
                )
                needs_bottom = needs_bottom or bool(
                    event.dynamic
                    or any(pitch.octave < 0 for pitch in event.pitches)
                )
            text_layouts = _measure_text_layout(measure, 0.0, cell.width, 0.0, style)
            if text_layouts:
                needs_bottom = True
                text_depth = max(
                    layout.bbox.y + layout.bbox.height for layout in text_layouts
                )
                bottom_extra = max(
                    bottom_extra,
                    max(0.0, text_depth - style.base_staff_height),
                )
    return (
        (style.system_top_reserve if needs_top else 0.0)
        + top_extra
        + (style.system_bottom_reserve if needs_bottom else 0.0)
        + bottom_extra
    )


def _page_chrome(
    scene: PublicationScene,
    style: PublicationStyle,
    title: str,
    score: JianpuScore,
    page_index: int,
    *,
    show_title: bool = True,
    show_page_number: bool = True,
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
    if page_index == 0 and show_title:
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
        meta += f"    ♩={score.tempo or DEFAULT_TEMPO}"
        scene.add(
            _text(
                "score-meta",
                style.margin_left,
                style.margin_top + 78,
                meta,
                style.meta_size,
            )
        )
    if show_page_number:
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


def _event_positions(
    events: list[Event],
    left: float,
    right: float,
    measure: Measure,
    style: PublicationStyle,
) -> list[float]:
    ideal_positions = [
        _event_x(event, index, len(events), left, right, measure)
        for index, event in enumerate(events)
    ]
    if not ideal_positions:
        return ideal_positions

    extents = [_event_visual_extents(event, style) for event in events]
    # No beat_boundaries here on purpose: the visible beat division is produced
    # by _apply_beat_boundary_gaps as a ratio after justification. Letting the
    # absolute beat_boundary_gap into the justification base would compound with
    # that ratio instead of acting as a floor. The absolute value earns its keep
    # in _intrinsic_measure_width (reserving cell room so the ratio stays
    # feasible) and in _apply_short_note_gaps (a floor the compaction may not
    # cross), both of which combine with the ratio by max().
    minimum_gaps = _minimum_event_gaps(
        events,
        extents,
        _common_shortest_duration(events),
        style,
    )
    minimum_relative = [0.0]
    for gap in minimum_gaps:
        minimum_relative.append(minimum_relative[-1] + gap)
    minimum_start = max(
        left - event_extent[0] - offset
        for event_extent, offset in zip(extents, minimum_relative, strict=True)
    )
    maximum_start = min(
        right - event_extent[1] - offset
        for event_extent, offset in zip(extents, minimum_relative, strict=True)
    )
    if minimum_start <= maximum_start and minimum_gaps:
        ideal_gaps = [
            max(0.0, ideal_positions[index] - ideal_positions[index - 1])
            for index in range(1, len(events))
        ]
        ideal_total = sum(ideal_gaps)
        gap_weights = [
            ideal_gap / ideal_total if ideal_total else 1.0 / len(minimum_gaps)
            for ideal_gap in ideal_gaps
        ]
        extra = maximum_start - minimum_start
        gaps = [
            minimum_gap + extra * weight
            for minimum_gap, weight in zip(minimum_gaps, gap_weights, strict=True)
        ]
        relative = [0.0]
        for gap in gaps:
            relative.append(relative[-1] + gap)
        start = minimum_start
    else:
        positions = _bounded_event_positions(
            events, extents, left, right, ideal_positions, style, measure
        )
        return positions
    positions = [start + offset for offset in relative]
    if _tuplet_run_count(events) == 1:
        index = 0
        while index < len(events):
            key = events[index].tuplet_id
            if not key:
                index += 1
                continue
            end = index + 1
            while end < len(events) and events[end].tuplet_id == key:
                end += 1
            count = end - index
            if count > 1:
                current_span = positions[end - 1] - positions[index]
                gap = min(
                    current_span / (count - 1),
                    max(18.0, style.minimum_event_gap * 0.72),
                )
                span = gap * (count - 1)
                center = (positions[index] + positions[end - 1]) / 2
                start = max(left, min(right - span, center - span / 2))
                for offset in range(count):
                    positions[index + offset] = start + offset * gap
            index = end
    _enforce_event_collisions(events, positions, style)
    # Beat boundaries first: it redistributes at constant span, so every gap
    # depends on the others' widths. Running it before the short-note control
    # keeps that control's effect local to short-note gaps.
    _apply_beat_boundary_gaps(events, positions, extents, measure, style)
    _apply_short_note_gaps(events, positions, extents, left, right, measure, style)
    _enforce_event_collisions(events, positions, style)
    return positions


def _enforce_event_collisions(
    events: list[Event], positions: list[float], style: PublicationStyle
) -> None:
    for index in range(1, len(events)):
        _previous_left, previous_right, _top, _bottom = _event_visual_extents(
            events[index - 1], style
        )
        current_left, _current_right, _top, _bottom = _event_visual_extents(
            events[index], style
        )
        positions[index] = max(
            positions[index],
            positions[index - 1]
            + previous_right
            - current_left
            + style.event_clearance,
        )


def _apply_short_note_gaps(
    events: list[Event],
    positions: list[float],
    extents: list[tuple[float, float, float, float]],
    left: float,
    right: float,
    measure: Measure,
    style: PublicationStyle,
) -> None:
    factor = style.short_note_gap_scale
    if factor == 1.0 or len(events) < 2:
        return
    eligible = [
        _is_short_note_pair(events[index - 1], events[index])
        for index in range(1, len(events))
    ]
    if not any(eligible):
        return
    base_gaps = [
        positions[index] - positions[index - 1] for index in range(1, len(positions))
    ]
    # Reuse the same hard floors the cell width reserved, so compaction cannot
    # flatten the beat division. The duration spring is deliberately excluded:
    # it is a preference the control is allowed to compress past.
    collision_gaps = _hard_event_gaps(events, extents, style, _beat_boundaries(measure))

    def candidate(
        candidate_factor: float,
    ) -> tuple[list[float], float, float]:
        gaps = [
            max(collision_gap, base_gap * candidate_factor) if is_eligible else base_gap
            for base_gap, collision_gap, is_eligible in zip(
                base_gaps, collision_gaps, eligible, strict=True
            )
        ]
        relative = [0.0]
        for gap in gaps:
            relative.append(relative[-1] + gap)
        minimum_start = max(
            left - extent[0] - offset
            for extent, offset in zip(extents, relative, strict=True)
        )
        maximum_start = min(
            right - extent[1] - offset
            for extent, offset in zip(extents, relative, strict=True)
        )
        return relative, minimum_start, maximum_start

    relative, minimum_start, maximum_start = candidate(factor)
    if minimum_start > maximum_start:
        if factor < 1.0:
            infeasible, feasible = factor, 1.0
            for _ in range(40):
                midpoint = (infeasible + feasible) / 2
                result = candidate(midpoint)
                if result[1] <= result[2]:
                    feasible = midpoint
                    relative, minimum_start, maximum_start = result
                else:
                    infeasible = midpoint
        else:
            feasible, infeasible = 1.0, factor
            relative, minimum_start, maximum_start = candidate(feasible)
            for _ in range(40):
                midpoint = (feasible + infeasible) / 2
                result = candidate(midpoint)
                if result[1] <= result[2]:
                    feasible = midpoint
                    relative, minimum_start, maximum_start = result
                else:
                    infeasible = midpoint

    original_center = (positions[0] + positions[-1]) / 2
    preferred_start = original_center - relative[-1] / 2
    start = max(minimum_start, min(maximum_start, preferred_start))
    for index, offset in enumerate(relative):
        positions[index] = start + offset


def _redistribute_eligible_gaps(
    positions: list[float],
    extents: list[tuple[float, float, float, float]],
    style: PublicationStyle,
    eligible: list[bool],
    locked: list[bool],
    factor: float,
) -> None:
    """Widen the gaps flagged in ``eligible`` by ``factor`` at constant span.

    A justified measure has no slack left, so the extra width is taken
    proportionally from the adjustable non-eligible gaps rather than from the
    margins. ``locked`` gaps neither widen nor donate, which keeps groups with
    their own spacing contract (tuplets) intact. The total span is preserved, so
    barlines do not move and the resulting ratio is independent of how far the
    justification pass stretched the measure. Collision floors still win; if
    they make the requested ratio infeasible a bisection retreats toward 1.0.
    """
    if factor == 1.0 or len(positions) < 2:
        return
    movable = [index for index, is_locked in enumerate(locked) if not is_locked]
    if not any(eligible[index] for index in movable):
        return
    if all(eligible[index] for index in movable):
        return
    base_gaps = [
        positions[index] - positions[index - 1] for index in range(1, len(positions))
    ]
    collision_gaps = [
        extents[index - 1][1] - extents[index][0] + style.event_clearance
        for index in range(1, len(extents))
    ]
    span = sum(base_gaps[index] for index in movable)
    if span <= 0:
        return

    def candidate(candidate_factor: float) -> list[float] | None:
        weights = [
            base_gaps[index] * (candidate_factor if eligible[index] else 1.0)
            for index in movable
        ]
        total = sum(weights)
        if total <= 0:
            return None
        scale = span / total
        gaps = list(base_gaps)
        for index, weight in zip(movable, weights, strict=True):
            gaps[index] = max(collision_gaps[index], weight * scale)
        if sum(gaps[index] for index in movable) > span + 1e-9:
            return None
        return gaps

    gaps = candidate(factor)
    if gaps is None:
        feasible, infeasible = 1.0, factor
        gaps = candidate(feasible)
        if gaps is None:
            return
        for _ in range(40):
            midpoint = (feasible + infeasible) / 2
            result = candidate(midpoint)
            if result is None:
                infeasible = midpoint
            else:
                feasible = midpoint
                gaps = result

    for index, gap in enumerate(gaps):
        positions[index + 1] = positions[index] + gap


def _apply_beat_boundary_gaps(
    events: list[Event],
    positions: list[float],
    extents: list[tuple[float, float, float, float]],
    measure: Measure,
    style: PublicationStyle,
) -> None:
    """Widen gaps that cross a beat boundary out of a subdivided beat.

    Applied after justification and at constant span, so the widening is a ratio
    against the neighbouring within-beat gaps rather than an absolute increment
    that the justification stretch would dilute. Tuplet gaps are locked out: a
    tuplet run carries its own even-spacing contract.
    """
    if len(events) < 2:
        return
    eligible = _subdivided_beat_crossings(events, _beat_boundaries(measure))
    locked = [
        _is_tuplet(events[index - 1]) or _is_tuplet(events[index])
        for index in range(1, len(events))
    ]
    _redistribute_eligible_gaps(
        positions,
        extents,
        style,
        eligible,
        locked,
        1.0 + style.beat_boundary_ratio,
    )


def _bounded_event_positions(
    events: list[Event],
    extents: list[tuple[float, float, float, float]],
    left: float,
    right: float,
    ideal_positions: list[float],
    style: PublicationStyle,
    measure: Measure | None = None,
) -> list[float]:
    """Project an overfull event sequence into the content bounds.

    The minimum collision constraints may be infeasible for an overfull bar.
    In that case preserving the barline boundary is more important than
    preserving every requested gap; actual collision reporting remains
    deterministic through the existing scene QA.
    """
    if len(events) == 1:
        extent = extents[0]
        minimum_center = left - extent[0]
        maximum_center = right - extent[1]
        if minimum_center > maximum_center:
            return [(left + right) / 2]
        return [max(minimum_center, min(maximum_center, ideal_positions[0]))]
    minimum_gaps = _minimum_event_gaps(
        events,
        extents,
        _common_shortest_duration(events),
        style,
        _beat_boundaries(measure) if measure is not None else None,
    )
    start = left - extents[0][0]
    end = right - extents[-1][1]
    total = sum(minimum_gaps)
    scale = (end - start) / total if total > 0 else 0.0
    positions = [start]
    for gap in minimum_gaps:
        positions.append(positions[-1] + gap * scale)
    for index, extent in enumerate(extents):
        positions[index] = max(
            left - extent[0], min(right - extent[1], positions[index])
        )
    for index in range(1, len(positions)):
        positions[index] = max(positions[index], positions[index - 1])
        positions[index] = min(positions[index], right - extents[index][1])
    for index in range(len(positions) - 2, -1, -1):
        positions[index] = min(positions[index], positions[index + 1])
        positions[index] = max(positions[index], left - extents[index][0])
    return positions


def _draw_event(
    scene: PublicationScene,
    style: PublicationStyle,
    event: Event,
    x: float,
    y: float,
    note_index: int,
    *,
    right_limit: float | None = None,
    note_group: int | None = None,
    playback_tick: int | None = None,
    part_index: int = 0,
    subtext_offset: float = 0.0,
) -> tuple[_Anchor, bool]:
    if event.kind == "extension":
        return _draw_extension_event(scene, event, x, y, right_limit=right_limit)
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
    layout_box = measure_event_ink(event, style, subtext_offset=subtext_offset)
    if right_limit is not None:
        layout_box = type(layout_box)(
            layout_box.left,
            layout_box.top,
            max(layout_box.left, min(layout_box.right, right_limit - x)),
            layout_box.bottom,
        )
    left, right, top, bottom = (
        layout_box.left,
        layout_box.right,
        layout_box.top,
        layout_box.bottom,
    )
    bbox = BBox(x + left, y + top, right - left, bottom - top)
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
        attrs["data-part-index"] = part_index
        if playback_tick is not None:
            attrs["data-playback-tick"] = playback_tick
        if note_group is not None:
            attrs["data-note-group"] = note_group
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
            _text(
                "note",
                x,
                y,
                "0",
                style.note_size,
                anchor="middle",
                attrs=_semantic_attrs(
                    "note", event.source_roles.get("note", source_ids)
                ),
            )
        )
    else:
        rows = pitch_layouts(event, style)
        for pitch_index, row in enumerate(rows):
            _draw_pitch(group, style, event, row.pitch, pitch_index, x, y + row.y)
    _draw_duration(group, event, x, y, style, right_limit=right_limit)
    if event.dynamic:
        dynamic_baseline = _dynamic_baseline(event, style) + subtext_offset
        group.children.append(
            _text(
                "dynamic",
                x,
                y + dynamic_baseline,
                event.dynamic,
                style.annotation_size,
                anchor="middle",
                attrs=_semantic_attrs("dynamic", event.source_roles.get("dynamic", [])),
            )
        )
    _draw_marks(group, event, x, y, style)
    scene.add(group)
    scene.register_sources(source_ids, bbox)
    return _Anchor(x, y, bbox, event), pitched


def _draw_extension_event(
    scene: PublicationScene,
    event: Event,
    x: float,
    y: float,
    *,
    right_limit: float | None = None,
) -> tuple[_Anchor, bool]:
    """Draw one beat-slot extension dash centered on its beat anchor."""

    left = x - 5.5
    right = x + 5.5
    if right_limit is not None:
        right = min(right, right_limit)
    top = y - 7.0
    bottom = y - 5.0
    bbox = BBox(left, top, max(0.0, right - left), bottom - top)
    attrs: dict[str, str | float | int] = {
        "class": "source-anchor",
        "data-note-token": event.source_token or "-",
        "data-bbox": bbox.as_data(),
    }
    group = SceneNode("g", attrs)
    if right > left:
        group.children.append(_line("extension-line", left, y - 6, right, y - 6, 1.7))
    scene.add(group)
    return _Anchor(x, y, bbox, event), False


def _draw_pitch(
    group: SceneNode,
    style: PublicationStyle,
    event: Event,
    pitch: JianpuPitch,
    pitch_index: int,
    x: float,
    y: float,
) -> None:
    note_ids = (
        [pitch.source_id] if pitch.source_id else event.source_roles.get("note", [])
    )
    accidental_ids = event.source_roles.get("accidental", [])
    exact_accidental_ids = (
        [pitch.accidental_source_id]
        if pitch.accidental_source_id
        else (
            [accidental_ids[pitch_index]]
            if pitch_index < len(accidental_ids)
            else accidental_ids
        )
    )
    accidental = _accidental_text(pitch)
    if accidental:
        registry = font_registry()
        note_value = str(max(0, min(7, pitch.degree)))
        note_left, note_top, _note_right, _note_bottom = registry.ink_bounds(
            note_value, style.note_size
        )
        note_left -= registry.measure(note_value, style.note_size) / 2
        _acc_left, _acc_top, accidental_right, accidental_bottom = registry.ink_bounds(
            accidental, style.accidental_size
        )
        note_advance = registry.measure(note_value, style.note_size)
        accidental_advance = registry.measure(accidental, style.accidental_size)
        accidental_right -= accidental_advance / 2
        accidental_bottom_target = y + note_top + 3.0
        accidental_x = min(
            x + note_left - style.accidental_clearance - accidental_right,
            x - note_advance / 2 - style.accidental_clearance - accidental_advance / 2,
        )
        accidental_y = accidental_bottom_target - accidental_bottom
        group.children.append(
            _text(
                "accidental",
                accidental_x,
                accidental_y,
                accidental,
                style.accidental_size,
                anchor="middle",
                attrs=_semantic_attrs("accidental", exact_accidental_ids),
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
            attrs=_semantic_attrs("note", note_ids),
        )
    )
    if pitch.octave:
        direction = -1 if pitch.octave > 0 else 1
        row = next(row for row in pitch_layouts(event, style) if row.pitch is pitch)
        if direction < 0:
            first_center = (
                y
                + (row.note_box.top - row.y)
                - style.event_clearance
                - style.octave_dot_radius
            )
        else:
            first_center = (
                y
                + (row.note_box.bottom - row.y)
                + style.event_clearance
                + style.octave_dot_radius
            )
        for index in range(abs(pitch.octave)):
            group.children.append(
                _circle(
                    "octave-dot",
                    x,
                    first_center + direction * index * style.rhythm_dot_step,
                    style.octave_dot_radius,
                    fill=True,
                )
            )


def _draw_duration(
    group: SceneNode,
    event: Event,
    x: float,
    y: float,
    style: PublicationStyle,
    *,
    right_limit: float | None = None,
) -> None:
    duration = event.duration
    if duration > 1:
        extensions = max(0, math.ceil(float(duration)) - 1)
        extension_start = _duration_extension_start(event, style)
        for index in range(extensions):
            ex1 = x + extension_start + index * style.extension_line_step
            ex2 = ex1 + 11
            if right_limit is not None:
                ex2 = min(ex2, right_limit)
            if ex2 <= ex1:
                continue
            group.children.append(_line("extension-line", ex1, y - 6, ex2, y - 6, 1.7))
    for index in range(event.dotted):
        dot_x = x + 17 + index * style.rhythm_dot_step
        if right_limit is not None and dot_x + style.rhythm_dot_radius > right_limit:
            continue
        group.children.append(
            _circle(
                "rhythm-dot",
                dot_x,
                y - 7,
                style.rhythm_dot_radius,
                fill=True,
            )
        )


def _draw_marks(
    group: SceneNode, event: Event, x: float, y: float, style: PublicationStyle
) -> None:
    layouts = mark_layouts(event, style)
    layouts_by_mark: dict[str, list[MarkLayout]] = {}
    for layout in layouts:
        layouts_by_mark.setdefault(layout.mark_id, []).append(layout)
    role_offsets = {"articulation": 0, "ornament": 0, "technical": 0}
    for mark_id, mark_group in layouts_by_mark.items():
        if mark_id in event.articulations or mark_id == event.articulation:
            role = "articulation"
        elif mark_id in event.ornaments:
            role = "ornament"
        else:
            role = "technical"
        role_ids = event.source_roles.get(role, [])
        role_index = role_offsets[role]
        exact_ids = [role_ids[role_index]] if role_index < len(role_ids) else role_ids
        role_offsets[role] += 1
        attrs = _semantic_attrs(role, exact_ids)
        for layout in mark_group:
            group.children.append(
                build_mark_graphic(
                    mark_id,
                    x + layout.x,
                    y + layout.y,
                    style,
                    role=role,
                    source_attrs=attrs,
                )
            )


def _draw_rhythm_lines(
    scene: PublicationScene,
    anchors: list[_Anchor],
    left_limit: float | None = None,
    right_limit: float | None = None,
    style: PublicationStyle | None = None,
    beat_boundaries: list[Fraction] | None = None,
) -> None:
    baseline_anchors = [
        anchor
        for anchor in anchors
        if (
            (_rhythm_line_count(anchor.event) > 0 and not anchor.event.beams)
            or any(beam.number.isdigit() for beam in anchor.event.beams)
        )
    ]
    shared_baseline = (
        max(
            (_rhythm_line_base(anchor, style) for anchor in baseline_anchors),
            default=0.0,
        )
        if style is not None
        else None
    )
    maximum_level = max(
        (
            max(
                _rhythm_line_count(anchor.event),
                max(
                    (
                        int(beam.number)
                        for beam in anchor.event.beams
                        if beam.number.isdigit()
                    ),
                    default=0,
                ),
            )
            for anchor in anchors
        ),
        default=0,
    )
    for level in range(1, maximum_level + 1):
        run: list[_Anchor] = []
        for anchor in [*anchors, None]:
            eligible = (
                anchor is not None
                and _rhythm_line_count(anchor.event) >= level
                and not anchor.event.beams
            )
            if eligible and (
                not run or _rhythm_events_connect(run[-1].event, anchor.event)
            ):
                run.append(anchor)
                continue
            if run:
                _draw_rhythm_run(
                    scene,
                    run,
                    level,
                    left_limit=left_limit,
                    right_limit=right_limit,
                    style=style,
                    baseline=shared_baseline,
                    beat_boundaries=beat_boundaries,
                )
                run = []
            if eligible and anchor is not None:
                run = [anchor]
        _draw_explicit_beam_level(
            scene,
            anchors,
            level,
            left_limit=left_limit,
            right_limit=right_limit,
            style=style,
            baseline=shared_baseline,
            beat_boundaries=beat_boundaries,
        )


def _split_anchors_by_beat(
    anchors: list[_Anchor], beat_boundaries: list[Fraction]
) -> list[list[_Anchor]]:
    interiors = [boundary for boundary in beat_boundaries if boundary > 0]
    groups: list[list[_Anchor]] = [[anchors[0]]] if anchors else []
    for previous, current in zip(anchors, anchors[1:]):
        prev_start = previous.event.start
        curr_start = current.event.start
        crossed = (
            prev_start is not None
            and curr_start is not None
            and any(prev_start < boundary <= curr_start for boundary in interiors)
        )
        if crossed:
            groups.append([current])
        else:
            groups[-1].append(current)
    return groups


def _draw_rhythm_segment(
    scene: PublicationScene,
    anchors: list[_Anchor],
    line_baseline: float,
    *,
    left_limit: float | None = None,
    right_limit: float | None = None,
    style: PublicationStyle | None = None,
    side_extent: float | None = None,
) -> None:
    source_ids = list(
        dict.fromkeys(
            source_id
            for anchor in anchors
            for source_id in (
                anchor.event.source_roles.get("note", []) or anchor.event.source_ids
            )
        )
    )
    if side_extent is None:
        side_extent = style.rhythm_line_side_extent if style else 12.0
    x1 = anchors[0].x - side_extent
    x2 = anchors[-1].x + side_extent
    if left_limit is not None:
        x1 = max(x1, left_limit)
    if right_limit is not None:
        x2 = min(x2, right_limit)
    if x2 <= x1:
        return
    stroke_width = 1.8
    source_ids_tuple = tuple(source_ids)
    layout = SpanLayout(
        "rhythm",
        BBox(
            x1,
            line_baseline - stroke_width / 2,
            x2 - x1,
            stroke_width,
        ),
        source_ids_tuple,
    )
    node = _line(
        "duration-line beam-line",
        x1,
        line_baseline,
        x2,
        line_baseline,
        stroke_width,
    )
    node.attrs.update(_span_attrs(layout))
    scene.add(node)
    scene.register_sources(list(layout.source_ids), layout.bbox)


def _draw_rhythm_run(
    scene: PublicationScene,
    anchors: list[_Anchor],
    level: int,
    *,
    left_limit: float | None = None,
    right_limit: float | None = None,
    style: PublicationStyle | None = None,
    baseline: float | None = None,
    beat_boundaries: list[Fraction] | None = None,
) -> None:
    line_baseline = (
        baseline
        if baseline is not None
        else max(_rhythm_line_base(anchor, style) for anchor in anchors)
    ) + (level - 1) * (style.rhythm_line_level_step if style else 6.0)
    if style is not None and style.break_beams_at_beat and beat_boundaries:
        groups = _split_anchors_by_beat(anchors, beat_boundaries)
        segment_extent: float | None = style.rhythm_line_break_segment_extent
    else:
        groups = [anchors]
        segment_extent = None
    for group in groups:
        _draw_rhythm_segment(
            scene,
            group,
            line_baseline,
            left_limit=left_limit,
            right_limit=right_limit,
            style=style,
            side_extent=segment_extent,
        )


def _draw_explicit_beam_level(
    scene: PublicationScene,
    anchors: list[_Anchor],
    level: int,
    *,
    left_limit: float | None = None,
    right_limit: float | None = None,
    style: PublicationStyle | None = None,
    baseline: float | None = None,
    beat_boundaries: list[Fraction] | None = None,
) -> None:
    runs: dict[tuple[str | None, str | None], list[_Anchor]] = {}
    for anchor in anchors:
        key = (anchor.event.staff, anchor.event.voice)
        run = runs.setdefault(key, [])
        status = next(
            (
                beam.status
                for beam in anchor.event.beams
                if beam.number.isdigit() and int(beam.number) == level
            ),
            None,
        )
        if status == "begin":
            if run:
                _draw_rhythm_run(
                    scene,
                    run,
                    level,
                    left_limit=left_limit,
                    right_limit=right_limit,
                    style=style,
                    baseline=baseline,
                    beat_boundaries=beat_boundaries,
                )
            runs[key] = [anchor]
        elif status == "continue" and run:
            run.append(anchor)
        elif status == "end" and run:
            run.append(anchor)
            _draw_rhythm_run(
                scene,
                run,
                level,
                left_limit=left_limit,
                right_limit=right_limit,
                style=style,
                baseline=baseline,
                beat_boundaries=beat_boundaries,
            )
            runs[key] = []
        elif status in {"forward-hook", "backward-hook"}:
            line_baseline = (
                baseline if baseline is not None else _rhythm_line_base(anchor, style)
            ) + (level - 1) * (style.rhythm_line_level_step if style else 6.0)
            if status == "forward-hook":
                hook_length = style.beam_hook_length if style else 18.0
                hook = [
                    _Anchor(anchor.x, anchor.y, anchor.bbox, anchor.event),
                    _Anchor(
                        anchor.x + hook_length,
                        anchor.y,
                        anchor.bbox,
                        anchor.event,
                    ),
                ]
            else:
                hook_length = style.beam_hook_length if style else 18.0
                hook = [
                    _Anchor(
                        anchor.x - hook_length,
                        anchor.y,
                        anchor.bbox,
                        anchor.event,
                    ),
                    _Anchor(anchor.x, anchor.y, anchor.bbox, anchor.event),
                ]
            x1 = hook[0].x
            x2 = hook[1].x
            if left_limit is not None:
                x1 = max(x1, left_limit)
            if right_limit is not None:
                x2 = min(x2, right_limit)
            if x2 <= x1:
                continue
            stroke_width = 1.8
            source_ids = tuple(
                anchor.event.source_roles.get("note", []) or anchor.event.source_ids
            )
            layout = SpanLayout(
                "beam-hook",
                BBox(
                    x1,
                    line_baseline - stroke_width / 2,
                    x2 - x1,
                    stroke_width,
                ),
                source_ids,
            )
            node = _line(
                "duration-line beam-line",
                x1,
                line_baseline,
                x2,
                line_baseline,
                stroke_width,
            )
            node.attrs.update(_span_attrs(layout))
            scene.add(node)
            scene.register_sources(list(layout.source_ids), layout.bbox)
        elif run:
            _draw_rhythm_run(
                scene,
                run,
                level,
                left_limit=left_limit,
                right_limit=right_limit,
                style=style,
                baseline=baseline,
                beat_boundaries=beat_boundaries,
            )
            runs[key] = []
    for run in runs.values():
        if run:
            _draw_rhythm_run(
                scene,
                run,
                level,
                left_limit=left_limit,
                right_limit=right_limit,
                style=style,
                baseline=baseline,
                beat_boundaries=beat_boundaries,
            )


def _rhythm_line_base(anchor: _Anchor, style: PublicationStyle | None = None) -> float:
    resolved_style = style or PublicationStyle()
    return anchor.y + _rhythm_line_offset(anchor.event, resolved_style)


def _rhythm_line_offset(event: Event, style: PublicationStyle) -> float:
    rows = pitch_layouts(event, style)
    note_bottom = max((row.note_box.bottom for row in rows), default=0.0)
    attachment_bottom = note_bottom
    for row in rows:
        for box in row.octave_boxes:
            attachment_bottom = max(attachment_bottom, box.bottom)
    return max(note_bottom + 12.5, attachment_bottom + 8.0)


def _is_tuplet(event: Event) -> bool:
    return bool(event.tuplet_id or event.tuplet_count or event.tuplet_spans)


def _rhythm_events_connect(previous: Event, current: Event) -> bool:
    if previous.voice != current.voice or previous.staff != current.staff:
        return False
    if previous.start is None or current.start is None:
        return True
    return previous.start + previous.duration == current.start


def _route_spanners(
    scene: PublicationScene,
    state: _OpenSpanners,
    anchor: _Anchor,
    left: float,
    right: float,
    style: PublicationStyle,
    *,
    lane: LaneKey = (None, "1"),
) -> None:
    event = anchor.event
    lane_state = state.lane(lane)
    for kind in ("tie", "slur", "slide"):
        start = bool(getattr(event, f"{kind}_start"))
        stop = bool(getattr(event, f"{kind}_stop"))
        current = getattr(lane_state, kind)
        if stop and current is not None:
            node = _spanner(
                kind,
                current,
                anchor,
                style=style,
                continuation_start=current.continuation_start,
            )
            scene.add(node)
            _register_span_node(scene, node)
            setattr(lane_state, kind, None)
            state.continuations.discard((lane, kind))
        if start:
            setattr(lane_state, kind, anchor)


def _start_spanner_continuations(
    state: _OpenSpanners,
    left: float,
    baseline: float,
    *,
    lane_offsets: dict[LaneKey, float] | None = None,
) -> None:
    for lane, kind in tuple(state.continuations):
        lane_state = state.lanes.get(lane)
        current = getattr(lane_state, kind) if lane_state is not None else None
        if current is None:
            state.continuations.discard((lane, kind))
            continue
        lane_baseline = baseline + (lane_offsets or {}).get(lane, 0.0)
        setattr(
            lane_state,
            kind,
            _Anchor(
                left + 3.0,
                lane_baseline,
                BBox(left + 3.0, lane_baseline - 20.0, 1.0, 40.0),
                current.event,
                continuation_start=True,
            ),
        )


def _finish_spanners(
    scene: PublicationScene,
    state: _OpenSpanners,
    right: float,
    staff_y: float,
    style: PublicationStyle,
) -> None:
    for lane, lane_state in state.lanes.items():
        for kind in ("tie", "slur", "slide"):
            current = getattr(lane_state, kind)
            if current is None:
                continue
            end = _Anchor(
                right - 3, current.y, BBox(right - 3, current.y, 1, 1), current.event
            )
            node = _spanner(kind, current, end, style=style, continuation=True)
            scene.add(node)
            _register_span_node(scene, node)
            state.continuations.add((lane, kind))


def _spanner(
    kind: str,
    start: _Anchor,
    end: _Anchor,
    style: PublicationStyle | None = None,
    continuation: bool = False,
    continuation_start: bool = False,
) -> SceneNode:
    resolved_style = style or PublicationStyle()
    if kind == "slide":
        delta = (
            -resolved_style.slide_endpoint_offset
            if (start.event.slide_direction or "up") == "up"
            else resolved_style.slide_endpoint_offset
        )
        d = (
            f"M {start.x + resolved_style.slide_endpoint_offset:g} {start.y - 3:g} "
            f"L {end.x - resolved_style.slide_endpoint_offset:g} {end.y + delta:g}"
        )
    else:
        sx, ex = (
            start.x + resolved_style.spanner_endpoint_offset,
            end.x - resolved_style.spanner_endpoint_offset,
        )
        if ex <= sx + 8:
            sx = start.x + 5
            ex = end.x - 5
        span = max(0.0, ex - sx)
        if kind == "slur":
            # Longer phrases need a slightly higher arch; short spans stay compact.
            height = -min(30.0, max(12.0, resolved_style.slur_height + span * 0.035))
            base = min(start.bbox.y, end.bbox.y) - resolved_style.spanner_base_clearance
            control_left = sx + span * 0.33
            control_right = sx + span * 0.67
            d = (
                f"M {sx:g} {base:g} C {control_left:g} {base + height:g} "
                f"{control_right:g} {base + height:g} {ex:g} {base:g}"
            )
        else:
            start_bottom = start.y + _event_attachment_bottom(
                start.event, resolved_style
            )
            end_bottom = end.y + _event_attachment_bottom(end.event, resolved_style)
            base = max(start_bottom, end_bottom) + resolved_style.tie_below_clearance
            thickness = 2.2
            height = max(4.0, min(12.0, resolved_style.tie_height))
            control_left = sx + span * 0.33
            control_right = sx + span * 0.67
            # Closed filled band, matching engraved ties and remaining stable at short spans.
            d = (
                f"M {sx:g} {base:g} C {control_left:g} {base + height:g} "
                f"{control_right:g} {base + height:g} {ex:g} {base:g} "
                f"C {control_right:g} {base + height - thickness:g} "
                f"{control_left:g} {base + height - thickness:g} {sx:g} {base:g} Z"
            )
    source_ids = list(
        dict.fromkeys(
            [
                *start.event.source_roles.get(f"{kind}_start", []),
                *end.event.source_roles.get(f"{kind}_stop", []),
            ]
        )
    )
    layout = _spanner_layout(
        kind,
        start,
        end,
        continuation=continuation,
        continuation_start=continuation_start,
        path_points=(
            (sx, base),
            (control_left, base + height),
            (control_right, base + height),
            (ex, base),
        )
        if kind != "slide"
        else (
            (
                start.x + resolved_style.slide_endpoint_offset,
                start.y - 3,
            ),
            (
                end.x - resolved_style.slide_endpoint_offset,
                end.y + delta,
            ),
        ),
        source_ids=tuple(source_ids),
    )
    attrs: dict[str, str | float | int] = {
        "class": kind,
        "d": d,
        **_span_attrs(layout, role=kind),
    }
    if continuation:
        attrs["data-continuation"] = "end"
    elif continuation_start:
        attrs["data-continuation"] = "start"
    return SceneNode("path", attrs)


def _spanner_layout(
    kind: str,
    start: _Anchor,
    end: _Anchor,
    *,
    continuation: bool,
    continuation_start: bool,
    path_points: tuple[tuple[float, float], ...],
    source_ids: tuple[str, ...],
) -> SpanLayout:
    stroke = 1.8
    xs = [point[0] for point in path_points]
    ys = [point[1] for point in path_points]
    return SpanLayout(
        kind,
        BBox(
            min(xs) - stroke / 2,
            min(ys) - stroke / 2,
            max(xs) - min(xs) + stroke,
            max(ys) - min(ys) + stroke,
        ),
        source_ids,
        "end" if continuation else "start" if continuation_start else "none",
    )


def _span_attrs(
    layout: SpanLayout, *, role: str = "note"
) -> dict[str, str | float | int]:
    attrs: dict[str, str | float | int] = {
        "data-bbox": layout.bbox.as_data(),
        "data-span-kind": layout.kind,
        "data-geometry-owner": f"span:{layout.kind}",
        **_semantic_attrs(role, list(layout.source_ids)),
    }
    if layout.continuation != "none":
        attrs["data-continuation"] = layout.continuation
    return attrs


def _register_span_node(scene: PublicationScene, node: SceneNode) -> None:
    raw_bbox = node.attrs.get("data-bbox")
    raw_ids = node.attrs.get("data-source-ids")
    if not raw_bbox or not raw_ids:
        return
    values = [float(value) for value in str(raw_bbox).split()]
    if len(values) != 4:
        return
    scene.register_sources(
        str(raw_ids).split(), BBox(values[0], values[1], values[2], values[3])
    )


def _draw_tuplets(
    scene: PublicationScene, anchors: list[_Anchor], style: PublicationStyle
) -> None:
    groups: dict[str, list[_Anchor]] = {}
    group_order: dict[str, int] = {}
    for anchor in anchors:
        for span in _event_tuplet_spans(anchor.event):
            if span.id not in group_order:
                group_order[span.id] = len(group_order)
            groups.setdefault(span.id, []).append(anchor)
    for span_id, group in sorted(groups.items(), key=lambda item: group_order[item[0]]):
        if not group:
            continue
        first, last = group[0], group[-1]
        count = first.event.tuplet_count or len(group)
        y = (
            min(_event_notation_top(anchor.event, anchor.y, style) for anchor in group)
            - style.tuplet_bracket_offset
            - group_order[span_id] * style.tuplet_stack_gap
        )
        center = (first.x + last.x) / 2
        number_width = _text_width(str(count), style.annotation_size)
        gap_half = max(8.0, number_width / 2 + style.tuplet_number_gap)
        source_ids = tuple(
            dict.fromkeys(
                source_id
                for item in group
                for source_id in item.event.source_roles.get("tuplet", [])
            )
        )
        arc_stroke = 1.4
        sx = first.x - style.tuplet_arc_extend
        ex = last.x + style.tuplet_arc_extend
        apex_y = y - style.tuplet_arc_height
        span = ex - sx
        gap_half = min(gap_half, span * 0.3)
        left_x = center - gap_half
        right_x = center + gap_half
        left_c1 = sx + (left_x - sx) * 0.35
        left_c2 = sx + (left_x - sx) * 0.85
        right_c1 = right_x + (ex - right_x) * 0.15
        right_c2 = right_x + (ex - right_x) * 0.65
        first_span = _tuplet_span_for_event(first.event, span_id)
        last_span = _tuplet_span_for_event(last.event, span_id)
        first_started = bool(first_span and first_span.start)
        last_stopped = bool(last_span and last_span.stop)
        continuation = (
            "start"
            if first_started and not last_stopped
            else "end"
            if last_stopped and not first_started
            else "none"
        )
        layout = SpanLayout(
            "tuplet",
            BBox(
                sx - arc_stroke / 2,
                apex_y - arc_stroke / 2,
                span + arc_stroke,
                style.tuplet_arc_height + arc_stroke,
            ),
            source_ids,
            continuation,
        )
        scene.add(
            SceneNode(
                "path",
                {
                    "class": "tuplet-bracket",
                    "d": (
                        f"M {sx:g} {y:g} "
                        f"C {left_c1:g} {apex_y:g} {left_c2:g} {apex_y:g} "
                        f"{left_x:g} {apex_y:g} "
                        f"M {right_x:g} {apex_y:g} "
                        f"C {right_c1:g} {apex_y:g} {right_c2:g} {apex_y:g} "
                        f"{ex:g} {y:g}"
                    ),
                    **_span_attrs(layout, role="tuplet"),
                },
            )
        )
        scene.register_sources(list(layout.source_ids), layout.bbox)
        _ink_left, ink_top, _ink_right, ink_bottom = font_registry().ink_bounds(
            str(count), style.annotation_size
        )
        number_baseline = apex_y - (ink_top + ink_bottom) / 2
        scene.add(
            _text(
                "tuplet-number",
                center,
                number_baseline,
                str(count),
                style.annotation_size,
                anchor="middle",
                attrs={
                    **_semantic_attrs("tuplet", list(layout.source_ids)),
                    "data-bbox": layout.bbox.as_data(),
                    "data-span-kind": "tuplet-number",
                },
            )
        )


def _event_tuplet_spans(event: Event) -> tuple[TupletSpan, ...]:
    if event.tuplet_spans:
        return tuple(event.tuplet_spans)
    if event.tuplet_id:
        return (
            TupletSpan(
                event.tuplet_id,
                start=event.tuplet_start,
                stop=event.tuplet_stop,
            ),
        )
    return ()


def _tuplet_span_for_event(event: Event, span_id: str) -> TupletSpan | None:
    return next(
        (span for span in _event_tuplet_spans(event) if span.id == span_id),
        None,
    )


def _event_notation_top(
    event: Event, baseline: float, style: PublicationStyle
) -> float:
    pitch_top = min(
        (
            min(
                row.note_box.top,
                row.accidental_box.top if row.accidental_box is not None else math.inf,
                *(box.top for box in row.octave_boxes),
            )
            for row in pitch_layouts(event, style)
        ),
        default=-style.note_size * 0.78,
    )
    mark_top = min(
        (mark.ink_box.top for mark in mark_layouts(event, style)),
        default=math.inf,
    )
    return baseline + min(pitch_top, mark_top)


def _measure_text_layout(
    measure: Measure,
    x: float,
    width: float,
    y: float,
    style: PublicationStyle,
) -> list[TextLayout]:
    event_dynamics = {event.dynamic for event in measure.events if event.dynamic}
    blocks = [
        block
        for block in measure.text_blocks
        if block.text
        and block.bbox is None
        and block.role != "measure_number"
        and block.direction_kind != "metronome"
        and not (block.role == "expression" and block.text in event_dynamics)
    ]
    lyric_anchors = {
        (block.text, block.lyric_verse or 1, block.start or Fraction(0))
        for block in blocks
        if block.role == "lyric"
    }
    for event in measure.events:
        lyrics = dict(event.lyrics)
        if event.lyric and 1 not in lyrics:
            lyrics[1] = event.lyric
        if event.kind != "note":
            continue
        for verse, text in lyrics.items():
            event_start = event.start or Fraction(0)
            event_end = event_start + event.duration
            already_positioned = any(
                block.role == "lyric"
                and block.text == text
                and (block.lyric_verse or 1) == verse
                and (
                    (block.start or Fraction(0)) == event_start
                    or (
                        block.duration is not None
                        and event_start <= (block.start or Fraction(0)) < event_end
                    )
                )
                for block in blocks
            )
            if already_positioned:
                continue
            anchor = (text, verse, event_start)
            if anchor in lyric_anchors:
                continue
            blocks.append(
                TextBlock(
                    text=text,
                    role="lyric",
                    measure_number=measure.display_number,
                    start=event_start,
                    lyric_verse=verse,
                    duration=None,
                )
            )
            lyric_anchors.add(anchor)
    if not blocks:
        return []

    event_bottom = max(
        (
            style.event_baseline
            + measure_event_ink(replace(event, lyric=None, lyrics={}), style).bottom
            for event in measure.events
        ),
        default=style.event_baseline,
    )
    inner_left = x + style.barline_gutter
    inner_right = x + width - style.barline_gutter
    layouts: list[TextLayout] = []
    previous_bottom = event_bottom
    verse_baselines: dict[int, float] = {}
    lyric_lane_bottom = event_bottom
    blocks.sort(
        key=lambda block: (
            0 if block.role == "lyric" else 1,
            (block.lyric_verse or 1) if block.role == "lyric" else 0,
            block.start or Fraction(0),
        )
    )
    for index, block in enumerate(blocks):
        font_size = block.font_size or (
            style.lyric_size if block.role == "lyric" else style.annotation_size
        )
        ink_left, ink_top, ink_right, ink_bottom = font_registry().ink_bounds(
            block.text, font_size
        )
        advance = font_registry().measure(block.text, font_size)
        if block.start is not None and measure.duration > 0:
            ratio = max(0.0, min(1.0, float(block.start / measure.duration)))
            center_x = inner_left + (inner_right - inner_left) * ratio
        else:
            center_x = x + width / 2
        if block.role == "lyric":
            verse = block.lyric_verse or 1
            if verse not in verse_baselines:
                _left, verse_top, _right, _bottom = font_registry().ink_bounds(
                    block.text, font_size
                )
                baseline = max(
                    y + style.base_staff_height + style.text_lane_clearance,
                    y
                    + max(
                        lyric_lane_bottom,
                        _measure_lyric_event_bottom(measure, style),
                    )
                    + style.text_lane_gap
                    - verse_top,
                )
                verse_baselines[verse] = baseline
            else:
                baseline = verse_baselines[verse]
        else:
            baseline = max(
                y + style.base_staff_height + style.text_lane_clearance,
                y + previous_bottom + style.text_lane_gap - ink_top,
            )
        bbox = BBox(
            center_x + ink_left - advance / 2,
            baseline + ink_top,
            ink_right - ink_left,
            ink_bottom - ink_top,
        )
        layouts.append(
            TextLayout(
                block.text,
                bbox,
                "lyric" if block.role == "lyric" else "annotation",
                index,
                font_size,
            )
        )
        if block.role != "lyric":
            previous_bottom = max(previous_bottom, bbox.y + bbox.height - y)
        else:
            lyric_lane_bottom = max(lyric_lane_bottom, bbox.y + bbox.height - y)
    return layouts


def _measure_lyric_event_bottom(measure: Measure, style: PublicationStyle) -> float:
    return max(
        (
            style.event_baseline + measure_event_ink(event, style).bottom
            for event in measure.events
            if event.kind == "note" and (event.lyric or event.lyrics)
        ),
        default=style.event_baseline,
    )


def _draw_measure_text(
    scene: PublicationScene,
    measure: Measure,
    x: float,
    y: float,
    width: float,
    style: PublicationStyle,
) -> None:
    for layout in _measure_text_layout(measure, x, width, y, style):
        _left, ink_top, _right, _bottom = font_registry().ink_bounds(
            layout.text, layout.font_size
        )
        node = _text(
            "lyric" if layout.role == "lyric" else "annotation",
            layout.bbox.x + layout.bbox.width / 2,
            layout.bbox.y - ink_top,
            layout.text,
            layout.font_size,
            anchor="middle",
        )
        node.attrs["data-bbox"] = layout.bbox.as_data()
        scene.add(node)


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
    events = [
        e
        for e in measure.events
        if not (e.kind == "rest" and e.hidden and e.tuplet_id is None)
    ]
    if len(events) == 1:
        event = events[0]
        if (
            event.generated
            and event.kind == "rest"
            and event.duration >= measure.duration
        ):
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
    resolved: list[Event] = []
    cursor = Fraction(0)
    for event in events:
        start = event.start if event.start is not None else cursor
        resolved.append(
            event if event.start is not None else replace(event, start=start)
        )
        cursor = start + event.duration
    return [piece for event in resolved for piece in _split_visual_event(event)]


def _split_visual_event(event: Event) -> list[Event]:
    if event.kind == "rest":
        return _split_long_rest(event)
    return _split_long_note(event)


def _split_long_note(event: Event) -> list[Event]:
    """Render a multi-beat note as beat slots (``1 - - -``), mirroring ``0 0 0 0``."""

    if (
        event.kind != "note"
        or not event.pitches
        or event.duration <= 1
        or event.tuplet_id
        or event.tuplet_count
        or event.tuplet_spans
    ):
        return [event]
    whole = int(event.duration)
    pieces: list[Fraction] = [Fraction(1)] * whole
    remainder = event.duration - whole
    note_dotted = event.dotted if remainder > 0 else 0
    if remainder > 0 and note_dotted == 0:
        pieces.append(remainder)
    result: list[Event] = []
    cursor = event.start
    for index, piece in enumerate(pieces):
        if index == 0:
            result.append(
                replace(event, duration=piece, dotted=note_dotted, start=cursor)
            )
        else:
            result.append(
                Event(
                    kind="extension",
                    duration=piece,
                    start=cursor,
                    voice=event.voice,
                    staff=event.staff,
                    source_token="-",
                )
            )
        if cursor is not None:
            cursor += piece
    return result


def _split_long_rest(event: Event) -> list[Event]:
    """Render a multi-beat rest as repeated quarter rests (0 0 0, not 0 - -)."""

    if (
        event.kind != "rest"
        or event.duration <= 1
        or event.tuplet_id
        or event.tuplet_count
        or event.tuplet_spans
    ):
        return [event]
    whole = int(event.duration)
    pieces: list[Fraction] = [Fraction(1)] * whole
    remainder = event.duration - whole
    if remainder > 0:
        pieces.append(remainder)
    result: list[Event] = []
    cursor = event.start
    for index, piece in enumerate(pieces):
        if index == 0:
            result.append(replace(event, duration=piece, dotted=0, start=cursor))
        else:
            result.append(
                Event(
                    kind="rest",
                    duration=piece,
                    dotted=_rest_piece_dots(piece),
                    start=cursor,
                    voice=event.voice,
                    staff=event.staff,
                    generated=event.generated,
                    measure_rest=event.measure_rest,
                )
            )
        if cursor is not None:
            cursor += piece
    return result


def _rest_piece_dots(duration: Fraction) -> int:
    for dots in range(1, 4):
        base = duration / (2 - Fraction(1, 2**dots))
        if 0 < base < 1 and is_notatable_duration(base):
            return dots
    return 0


_ACCIDENTAL_RENDER_GLYPH = {"n": "♮"}


def _accidental_text(pitch: JianpuPitch) -> str:
    if pitch.accidental_text:
        return _ACCIDENTAL_RENDER_GLYPH.get(
            pitch.accidental_text, pitch.accidental_text
        )
    value = pitch.accidental
    return {
        Fraction(2): "𝄪",
        Fraction(1): "♯",
        Fraction(1, 2): "↑",
        Fraction(-1, 2): "↓",
        Fraction(-1): "♭",
        Fraction(-2): "𝄫",
    }.get(value, "" if value == 0 else f"{float(value):+g}")


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
    attrs: dict[str, str | float | int] | None = None,
) -> SceneNode:
    node_attrs: dict[str, str | float | int] = {
        "class": cls,
        "x": x,
        "y": y,
        "font-size": size,
        "text-anchor": anchor,
    }
    ink_left, ink_top, ink_right, ink_bottom = font_registry().ink_bounds(value, size)
    advance = font_registry().measure(value, size)
    offset = (
        -advance / 2 if anchor == "middle" else -advance if anchor == "end" else 0.0
    )
    node_attrs.setdefault(
        "data-bbox",
        BBox(
            x + offset + ink_left,
            y + ink_top,
            ink_right - ink_left,
            ink_bottom - ink_top,
        ).as_data(),
    )
    node_attrs.update(attrs or {})
    return SceneNode(
        "text",
        node_attrs,
        value,
    )


def _semantic_attrs(role: str, source_ids: list[str]) -> dict[str, str]:
    unique = list(dict.fromkeys(source_id for source_id in source_ids if source_id))
    if not unique:
        return {}
    return {"data-source-role": role, "data-source-ids": " ".join(unique)}


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
