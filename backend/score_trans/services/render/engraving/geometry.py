from __future__ import annotations

import math
from dataclasses import dataclass

from ....domain.performance_marks import get_performance_mark
from ....models.score import Event, JianpuPitch
from .fonts import font_registry
from .style import PublicationStyle


@dataclass(frozen=True, slots=True)
class InkBox:
    """A rectangle in coordinates relative to an event anchor."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    def union(self, other: InkBox) -> InkBox:
        return InkBox(
            min(self.left, other.left),
            min(self.top, other.top),
            max(self.right, other.right),
            max(self.bottom, other.bottom),
        )


@dataclass(frozen=True, slots=True)
class VisualPart:
    role: str
    ink_box: InkBox


@dataclass(frozen=True, slots=True)
class EventLayout:
    ink_box: InkBox
    parts: tuple[VisualPart, ...]


@dataclass(frozen=True, slots=True)
class PitchLayout:
    pitch: JianpuPitch
    y: float
    note_box: InkBox
    accidental_box: InkBox | None
    octave_boxes: tuple[InkBox, ...]


@dataclass(frozen=True, slots=True)
class MarkLayout:
    mark_id: str
    role: str
    label: str
    x: float
    y: float
    ink_box: InkBox
    is_staccato: bool


def _empty_box() -> InkBox:
    return InkBox(0.0, 0.0, 0.0, 0.0)


def _centered_text_box(value: str, size: float) -> InkBox:
    registry = font_registry()
    left, top, right, bottom = registry.ink_bounds(value, size)
    advance = registry.measure(value, size)
    return InkBox(left - advance / 2, top, right - advance / 2, bottom)


def _translated(box: InkBox, x: float, y: float) -> InkBox:
    return InkBox(box.left + x, box.top + y, box.right + x, box.bottom + y)


def pitch_layouts(event: Event, style: PublicationStyle) -> tuple[PitchLayout, ...]:
    """Return pitch rows with attachment-aware vertical spacing."""

    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    if not pitches:
        return ()

    offsets = [
        -(len(pitches) - 1) * style.chord_gap / 2 + index * style.chord_gap
        for index in range(len(pitches))
    ]

    def build(row_offsets: list[float]) -> list[PitchLayout]:
        layouts: list[PitchLayout] = []
        for pitch, row_y in zip(pitches, row_offsets):
            value = str(max(0, min(7, pitch.degree)))
            note_box = _translated(
                _centered_text_box(value, style.note_size), 0.0, row_y
            )
            accidental_box = None
            accidental = _accidental_text(pitch)
            if accidental:
                accidental_rel = _centered_text_box(accidental, style.accidental_size)
                note_advance = font_registry().measure(value, style.note_size)
                accidental_advance = font_registry().measure(
                    accidental, style.accidental_size
                )
                accidental_x = min(
                    note_box.left - style.accidental_clearance - accidental_rel.right,
                    -note_advance / 2
                    - style.accidental_clearance
                    - accidental_advance / 2,
                )
                accidental_y = note_box.top + 3.0 - accidental_rel.bottom
                accidental_box = _translated(accidental_rel, accidental_x, accidental_y)
            octave_boxes: list[InkBox] = []
            if pitch.octave:
                direction = -1 if pitch.octave > 0 else 1
                if direction < 0:
                    first_center = (
                        note_box.top - style.event_clearance - style.octave_dot_radius
                    )
                else:
                    first_center = (
                        note_box.bottom
                        + style.event_clearance
                        + style.octave_dot_radius
                    )
                for dot_index in range(abs(pitch.octave)):
                    cy = first_center + direction * dot_index * style.rhythm_dot_step
                    radius = style.octave_dot_radius
                    octave_boxes.append(
                        InkBox(-radius, cy - radius, radius, cy + radius)
                    )
            layouts.append(
                PitchLayout(pitch, row_y, note_box, accidental_box, tuple(octave_boxes))
            )
        return layouts

    for index in range(1, len(pitches)):
        current = build(offsets)
        previous_bottom = current[index - 1].note_box.bottom
        for box in (
            current[index - 1].accidental_box,
            *current[index - 1].octave_boxes,
        ):
            if box is not None:
                previous_bottom = max(previous_bottom, box.bottom)
        current_top = current[index].note_box.top
        accidental_box = current[index].accidental_box
        if accidental_box is not None:
            current_top = min(current_top, accidental_box.top)
        for box in current[index].octave_boxes:
            current_top = min(current_top, box.top)
        required = previous_bottom + style.event_clearance - current_top
        if required > 0:
            for shift_index in range(index, len(offsets)):
                offsets[shift_index] += required

    center = (offsets[0] + offsets[-1]) / 2
    offsets = [offset - center for offset in offsets]
    return tuple(build(offsets))


def _accidental_text(pitch: JianpuPitch) -> str:
    if pitch.accidental_text:
        return pitch.accidental_text
    value = pitch.accidental
    values = {
        2: "𝄪",
        1: "♯",
        0.5: "↑",
        -0.5: "↓",
        -1: "♭",
        -2: "𝄫",
    }
    return values.get(float(value), "" if value == 0 else f"{float(value):+g}")


def _mark_label(mark_id: str) -> str:
    spec = get_performance_mark(mark_id)
    renderer = spec.renderer if spec else mark_id
    return {
        "accent": ">",
        "tenuto": "—",
        "staccato": "▼",
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
    }.get(renderer, mark_id)


def mark_layouts(event: Event, style: PublicationStyle) -> tuple[MarkLayout, ...]:
    rows = pitch_layouts(event, style)
    attachment_top = min((row.note_box.top for row in rows), default=-31.0)
    attachment_bottom = max((row.note_box.bottom for row in rows), default=0.0)
    horizontal_left = min((row.note_box.left for row in rows), default=-7.0)
    horizontal_right = max((row.note_box.right for row in rows), default=7.0)
    for row in rows:
        if row.accidental_box is not None:
            attachment_top = min(attachment_top, row.accidental_box.top)
            horizontal_left = min(horizontal_left, row.accidental_box.left)
            horizontal_right = max(horizontal_right, row.accidental_box.right)
        for dot_box in row.octave_boxes:
            attachment_top = min(attachment_top, dot_box.top)
            attachment_bottom = max(attachment_bottom, dot_box.bottom)

    if event.dotted:
        horizontal_right = max(
            horizontal_right,
            17.0
            + (event.dotted - 1) * style.rhythm_dot_step
            + style.rhythm_dot_radius,
        )
    if event.duration > 1:
        extensions = max(0, math.ceil(float(event.duration)) - 1)
        if extensions:
            extension_start = _duration_extension_start(event, style)
            horizontal_right = max(
                horizontal_right,
                extension_start
                + (extensions - 1) * style.extension_line_step
                + 11.0,
            )

    mark_ids = list(
        dict.fromkeys([*event.articulations, *event.ornaments, *event.technical])
    )
    if event.articulation and event.articulation not in mark_ids:
        mark_ids.insert(0, event.articulation)

    placement_counts: dict[str, int] = {}
    above_cursor = attachment_top - style.event_clearance
    below_right_cursor = attachment_bottom + style.event_clearance
    layouts: list[MarkLayout] = []
    for mark_id in mark_ids:
        if mark_id in event.articulations or mark_id == event.articulation:
            role = "articulation"
        elif mark_id in event.ornaments:
            role = "ornament"
        else:
            role = "technical"
        spec = get_performance_mark(mark_id)
        placement = spec.placement if spec else "above"
        placement_index = placement_counts.get(placement, 0)
        placement_counts[placement] = placement_index + 1
        label = _mark_label(mark_id)
        is_staccato = mark_id == "staccato"
        if is_staccato:
            radius = style.staccato_radius
            base_box = InkBox(-radius, -radius, radius, radius)
        else:
            base_box = _centered_text_box(label, style.annotation_size)
        if placement == "left":
            x = (
                horizontal_left
                - style.mark_clearance
                - base_box.right
                - placement_index * (base_box.width + style.mark_stack_gap)
            )
            y = -2.0
        elif placement == "right":
            x = (
                horizontal_right
                + style.mark_clearance
                - base_box.left
                + placement_index * (base_box.width + style.mark_stack_gap)
            )
            y = -2.0
        elif placement == "below-right":
            x = horizontal_right + style.mark_clearance
            y = below_right_cursor - base_box.top
            below_right_cursor = y + base_box.bottom + style.mark_stack_gap
        else:
            x = 0.0
            y = above_cursor - base_box.bottom
            above_cursor = y + base_box.top - style.mark_stack_gap
        ink_box = _translated(base_box, x, y)
        layouts.append(MarkLayout(mark_id, role, label, x, y, ink_box, is_staccato))
    return tuple(layouts)


def _rhythm_line_count(event: Event) -> int:
    duration = event.duration
    count = 0
    unit = 1
    while duration > 0 and duration < unit and count < 4:
        count += 1
        unit /= 2
    return count


def _duration_extension_start(event: Event, style: PublicationStyle) -> float:
    if not event.dotted:
        return 17.0
    return (
        17.0
        + max(0, event.dotted - 1) * style.rhythm_dot_step
        + style.rhythm_dot_radius
        + style.duration_dot_clearance
    )


def _is_tuplet(event: Event) -> bool:
    return bool(event.tuplet_id or event.tuplet_count or event.tuplet_spans)


def _event_attachment_bottom(event: Event, style: PublicationStyle) -> float:
    rows = pitch_layouts(event, style)
    note_bottom = max((row.note_box.bottom for row in rows), default=0.0)
    attachment_bottom = note_bottom
    for row in rows:
        for box in row.octave_boxes:
            attachment_bottom = max(attachment_bottom, box.bottom)
    if not _is_tuplet(event):
        rhythm_lines = _rhythm_line_count(event)
        if rhythm_lines:
            rhythm_base = max(note_bottom + 12.5, attachment_bottom + 8.0)
            attachment_bottom = max(
                attachment_bottom,
                rhythm_base + (rhythm_lines - 1) * 6.0 + style.stroke_width,
            )
    return attachment_bottom


def _dynamic_baseline(event: Event, style: PublicationStyle) -> float:
    if not event.dynamic:
        return 63.0
    _left, ink_top, _right, _bottom = font_registry().ink_bounds(
        event.dynamic, style.annotation_size
    )
    return max(
        63.0,
        _event_attachment_bottom(event, style)
        + style.dynamic_clearance
        - ink_top,
    )


def _lyric_baseline(event: Event, style: PublicationStyle) -> float:
    if not event.lyric:
        return 44.0
    _left, lyric_top, _right, _bottom = font_registry().ink_bounds(
        event.lyric, style.lyric_size
    )
    baseline = max(
        44.0,
        _event_attachment_bottom(event, style) + style.lyric_clearance - lyric_top,
    )
    if event.dynamic:
        dynamic_box = _centered_text_box(event.dynamic, style.annotation_size)
        dynamic_bottom = _dynamic_baseline(event, style) + dynamic_box.bottom
        baseline = max(
            baseline,
            dynamic_bottom + style.lyric_clearance - lyric_top,
        )
    return baseline


def measure_event_layout(event: Event, style: PublicationStyle) -> EventLayout:
    """Measure every visible event component with one conservative geometry pass."""

    parts: list[VisualPart] = []
    pitch_rows = pitch_layouts(event, style)
    if pitch_rows:
        for row in pitch_rows:
            parts.append(VisualPart("note", row.note_box))
    else:
        parts.append(VisualPart("note", _centered_text_box("0", style.note_size)))

    box = _empty_box()
    for part in parts:
        box = box.union(part.ink_box)

    for row in pitch_rows:
        if row.accidental_box is not None:
            parts.append(VisualPart("accidental", row.accidental_box))
            box = box.union(row.accidental_box)
        for dot_box in row.octave_boxes:
            parts.append(VisualPart("octave-dot", dot_box))
            box = box.union(dot_box)

    if event.duration > 1:
        extensions = max(0, math.ceil(float(event.duration)) - 1)
        if extensions:
            left = _duration_extension_start(event, style)
            right = left + (extensions - 1) * style.extension_line_step + 11
            box = box.union(InkBox(left, -7, right, -5))
            parts.append(VisualPart("extension-line", InkBox(left, -7, right, -5)))
    if event.dotted:
        right = (
            17 + (event.dotted - 1) * style.rhythm_dot_step + style.rhythm_dot_radius
        )
        box = box.union(
            InkBox(
                17 - style.rhythm_dot_radius,
                -7 - style.rhythm_dot_radius,
                right,
                -7 + style.rhythm_dot_radius,
            )
        )
        parts.append(
            VisualPart(
                "rhythm-dot",
                InkBox(
                    17 - style.rhythm_dot_radius,
                    -7 - style.rhythm_dot_radius,
                    right,
                    -7 + style.rhythm_dot_radius,
                ),
            )
        )

    chord_bottom = max((row.note_box.bottom for row in pitch_rows), default=0.0)
    attachment_bottom = chord_bottom
    for row in pitch_rows:
        for dot_box in row.octave_boxes:
            attachment_bottom = max(attachment_bottom, dot_box.bottom)
    if not _is_tuplet(event):
        rhythm_lines = _rhythm_line_count(event)
        if rhythm_lines:
            rhythm_base = max(chord_bottom + 12.5, attachment_bottom + 8.0)
            box = box.union(
                InkBox(
                    -12,
                    rhythm_base,
                    12,
                    rhythm_base + (rhythm_lines - 1) * 6 + style.stroke_width,
                )
            )
    if event.lyric:
        lyric_baseline = _lyric_baseline(event, style)
        lyric_box = _translated(
            _centered_text_box(event.lyric, style.lyric_size), 0.0, lyric_baseline
        )
        parts.append(VisualPart("lyric", lyric_box))
        box = box.union(lyric_box)
    if event.dynamic:
        dynamic_baseline = _dynamic_baseline(event, style)
        dynamic_box = _translated(
            _centered_text_box(event.dynamic, style.annotation_size),
            0.0,
            dynamic_baseline,
        )
        parts.append(VisualPart("dynamic", dynamic_box))
        box = box.union(dynamic_box)

    for mark in mark_layouts(event, style):
        parts.append(VisualPart("mark", mark.ink_box))
        box = box.union(mark.ink_box)
    return EventLayout(box, tuple(parts))


def measure_event_ink(event: Event, style: PublicationStyle) -> InkBox:
    return measure_event_layout(event, style).ink_box
