from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from ....domain.jianpu_tokens import tuplet_normal_notes
from ....domain.performance_marks import get_performance_mark
from ....models.score import Event, JianpuPitch
from .fonts import font_registry
from .mark_graphics import mark_graphic_box
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
    chorded: bool = False


def _chord_box(box: InkBox, style: PublicationStyle) -> InkBox:
    """Apply the publication chord profile to a regular relative ink box."""
    return InkBox(
        box.left * style.chord_scale_x,
        box.top * style.chord_scale_y,
        box.right * style.chord_scale_x,
        box.bottom * style.chord_scale_y,
    )


def _chorded(event: Event) -> bool:
    return len(event.pitches) > 1


def _chord_rhythm_scale(event: Event, style: PublicationStyle) -> float:
    return style.chord_rhythm_scale if _chorded(event) else 1.0


@dataclass(frozen=True, slots=True)
class MarkLayout:
    mark_id: str
    role: str
    x: float
    y: float
    ink_box: InkBox


def _empty_box() -> InkBox:
    return InkBox(0.0, 0.0, 0.0, 0.0)


def _centered_text_box(value: str, size: float, weight: int = 400) -> InkBox:
    registry = font_registry()
    left, top, right, bottom = registry.ink_bounds(value, size, weight)
    advance = registry.measure(value, size, weight)
    return InkBox(left - advance / 2, top, right - advance / 2, bottom)


def _left_aligned_text_box(value: str, size: float, weight: int = 500) -> InkBox:
    """Text ink box starting at the origin and extending rightward by advance.

    Used for left-aligned lyrics whose left edge sits at the note centre
    rather than being centred on it.
    """
    registry = font_registry()
    left, top, _right, bottom = registry.ink_bounds(value, size, weight)
    advance = registry.measure(value, size, weight)
    return InkBox(left, top, advance, bottom)


_EAST_ASIAN_RANGES = (
    (0x2E80, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2FA1F),
)
_LYRIC_PREFIX_PUNCTUATION = "([{（《〈「『【“‘"
_LYRIC_SUFFIX_PUNCTUATION = ",.!?;:!?！？；：，。、)]}）》〉」』】”’…—~"


def lyric_text_box(text: str, size: float, *, melisma: bool = False) -> InkBox:
    """Return a lyric's full ink box relative to its musical note anchor."""
    if melisma:
        return _left_aligned_text_box(text, size)
    registry = font_registry()
    if any(
        any(start <= ord(char) <= end for start, end in _EAST_ASIAN_RANGES)
        for char in text
    ):
        prefix = 0
        while prefix < len(text) and text[prefix] in _LYRIC_PREFIX_PUNCTUATION:
            prefix += 1
        suffix = len(text)
        while suffix > prefix and text[suffix - 1] in _LYRIC_SUFFIX_PUNCTUATION:
            suffix -= 1
        prefix_width = registry.measure(text[:prefix], size, 500)
        core_width = registry.measure(text[prefix:suffix], size, 500)
        left = -prefix_width - core_width / 2
        _ink_left, top, _ink_right, bottom = registry.ink_bounds(text, size, 500)
        advance = registry.measure(text, size, 500)
        return InkBox(left, top, left + advance, bottom)
    return _centered_text_box(text, size, 500)


def _translated(box: InkBox, x: float, y: float) -> InkBox:
    return InkBox(box.left + x, box.top + y, box.right + x, box.bottom + y)


def pitch_layouts(event: Event, style: PublicationStyle) -> tuple[PitchLayout, ...]:
    """Return pitch rows with attachment-aware vertical spacing."""

    pitches = sorted(event.pitches, key=lambda pitch: pitch.rank, reverse=True)
    if not pitches:
        return ()

    # Align the lowest chord tone with the event baseline; stack higher tones
    # above it. Centering the whole chord moved its bottom tone below other
    # notes at the same rhythmic position.
    chorded = len(pitches) > 1
    layer_gap = style.chord_layer_gap if chorded else style.chord_gap
    dot_scale = style.chord_octave_dot_scale if chorded else 1.0
    offsets = [-(len(pitches) - index - 1) * layer_gap for index in range(len(pitches))]

    def build(row_offsets: list[float]) -> list[PitchLayout]:
        note_boxes = []
        for pitch, row_y in zip(pitches, row_offsets, strict=True):
            box = _centered_text_box(
                str(max(0, min(7, pitch.degree))), style.note_size, 500
            )
            if chorded:
                box = _chord_box(box, style)
            note_boxes.append(_translated(box, 0.0, row_y))
        note_bottom = max(box.bottom for box in note_boxes)
        layouts: list[PitchLayout] = []
        for pitch, row_y, note_box in zip(
            pitches, row_offsets, note_boxes, strict=True
        ):
            value = str(max(0, min(7, pitch.degree)))
            accidental_box = None
            accidental = _accidental_text(pitch)
            if accidental:
                accidental_rel = _centered_text_box(accidental, style.accidental_size)
                if chorded:
                    accidental_rel = _chord_box(accidental_rel, style)
                note_advance = font_registry().measure(value, style.note_size, 500) * (
                    style.chord_scale_x if chorded else 1.0
                )
                accidental_advance = font_registry().measure(
                    accidental, style.accidental_size
                ) * (style.chord_scale_x if chorded else 1.0)
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
                        note_box.top
                        - style.event_clearance
                        - style.octave_dot_radius * dot_scale
                    )
                else:
                    first_center = _low_octave_first_center(
                        event, row_y, note_box.bottom, note_bottom, style
                    )
                for dot_index in range(abs(pitch.octave)):
                    cy = (
                        first_center
                        + direction * dot_index * style.rhythm_dot_step * dot_scale
                    )
                    radius = style.octave_dot_radius * dot_scale
                    octave_boxes.append(
                        InkBox(-radius, cy - radius, radius, cy + radius)
                    )
            layouts.append(
                PitchLayout(
                    pitch, row_y, note_box, accidental_box, tuple(octave_boxes), chorded
                )
            )
        low_octave_rows = sorted(
            enumerate(layouts),
            key=lambda item: item[1].y,
        )
        previous_bottom = -math.inf
        for layout_index, layout in low_octave_rows:
            if layout.pitch.octave >= 0:
                continue
            boxes = list(layout.octave_boxes)
            if not boxes:
                continue
            first_center = (boxes[0].top + boxes[0].bottom) / 2
            shift = max(
                0.0,
                previous_bottom + style.rhythm_dot_step * dot_scale - first_center,
            )
            if shift:
                boxes = [
                    InkBox(box.left, box.top + shift, box.right, box.bottom + shift)
                    for box in boxes
                ]
            previous_bottom = max(box.bottom for box in boxes)
            layouts[layout_index] = PitchLayout(
                layout.pitch,
                layout.y,
                layout.note_box,
                layout.accidental_box,
                tuple(boxes),
                layout.chorded,
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
            for shift_index in range(index):
                offsets[shift_index] -= required

    layouts = list(build(offsets))
    if not _rhythm_line_count(event):
        for index in range(1, len(layouts)):
            previous = layouts[index - 1]
            previous_bottom = previous.note_box.bottom
            for box in (previous.accidental_box, *previous.octave_boxes):
                if box is not None:
                    previous_bottom = max(previous_bottom, box.bottom)
            current = layouts[index]
            current_top = current.note_box.top
            if current.accidental_box is not None:
                current_top = min(current_top, current.accidental_box.top)
            for box in current.octave_boxes:
                current_top = min(current_top, box.top)
            required = previous_bottom + style.event_clearance - current_top
            if required <= 0:
                continue
            for shift_index in range(index):
                shifted = layouts[shift_index]
                layouts[shift_index] = PitchLayout(
                    shifted.pitch,
                    shifted.y - required,
                    _translated(shifted.note_box, 0.0, -required),
                    (
                        _translated(shifted.accidental_box, 0.0, -required)
                        if shifted.accidental_box is not None
                        else None
                    ),
                    tuple(
                        _translated(box, 0.0, -required) for box in shifted.octave_boxes
                    ),
                    shifted.chorded,
                )
    return tuple(layouts)


_ACCIDENTAL_RENDER_GLYPH = {"n": "♮"}


def _accidental_text(pitch: JianpuPitch) -> str:
    if pitch.accidental_text:
        return _ACCIDENTAL_RENDER_GLYPH.get(
            pitch.accidental_text, pitch.accidental_text
        )
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


def _below_right_anchors(
    event: Event, rows: tuple[PitchLayout, ...], style: PublicationStyle
) -> list[tuple[float, float]]:
    """Per-note (right, bottom) anchors for below-right marks.

    Every chord tone gets its own anchor at its note's bottom-right corner
    (octave dots below the note extend the bottom).
    """

    if not rows:
        rest_box = _centered_text_box("0", style.note_size, 500)
        anchors = [(rest_box.right, rest_box.bottom)]
    else:
        anchors = []
        for row in rows:
            bottom = row.note_box.bottom
            for dot_box in row.octave_boxes:
                bottom = max(bottom, dot_box.bottom)
            anchors.append((row.note_box.right, bottom))
    return anchors


def mark_layouts(event: Event, style: PublicationStyle) -> tuple[MarkLayout, ...]:
    rows = pitch_layouts(event, style)
    attachment_top = min((row.note_box.top for row in rows), default=-31.0)
    horizontal_left = min((row.note_box.left for row in rows), default=-7.0)
    horizontal_right = max((row.note_box.right for row in rows), default=7.0)
    for row in rows:
        if row.accidental_box is not None:
            attachment_top = min(attachment_top, row.accidental_box.top)
            horizontal_left = min(horizontal_left, row.accidental_box.left)
            horizontal_right = max(horizontal_right, row.accidental_box.right)
        for dot_box in row.octave_boxes:
            attachment_top = min(attachment_top, dot_box.top)

    rhythm_scale = _chord_rhythm_scale(event, style)
    if event.dotted:
        horizontal_right = max(
            horizontal_right,
            17.0 * rhythm_scale
            + (event.dotted - 1) * style.rhythm_dot_step * rhythm_scale
            + style.rhythm_dot_radius * rhythm_scale,
        )
    if event.duration > 1:
        extensions = max(0, math.ceil(float(event.duration)) - 1)
        if extensions:
            extension_start = _duration_extension_start(event, style)
            horizontal_right = max(
                horizontal_right,
                extension_start
                + ((extensions - 1) * style.extension_line_step + 11.0) * rhythm_scale,
            )

    mark_ids = list(
        dict.fromkeys([*event.articulations, *event.ornaments, *event.technical])
    )
    if event.articulation and event.articulation not in mark_ids:
        mark_ids.insert(0, event.articulation)

    placement_counts: dict[str, int] = {}
    above_cursor = attachment_top - style.event_clearance
    below_right_anchors = _below_right_anchors(event, rows, style)
    below_right_cursors: dict[int, float] = {}
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
        mark_box = mark_graphic_box(mark_id, style)
        base_box = InkBox(
            mark_box.x,
            mark_box.y,
            mark_box.x + mark_box.width,
            mark_box.y + mark_box.height,
        )
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
            for anchor_index, (anchor_right, anchor_bottom) in enumerate(
                below_right_anchors
            ):
                cursor = below_right_cursors.get(
                    anchor_index, anchor_bottom - base_box.height / 2
                )
                mark_x = anchor_right + style.mark_clearance
                mark_y = cursor - base_box.top
                below_right_cursors[anchor_index] = (
                    mark_y + base_box.bottom + style.mark_stack_gap
                )
                layouts.append(
                    MarkLayout(
                        mark_id,
                        role,
                        mark_x,
                        mark_y,
                        _translated(base_box, mark_x, mark_y),
                    )
                )
            continue
        else:
            x = 0.0
            y = above_cursor - base_box.bottom
            above_cursor = y + base_box.top - style.mark_stack_gap
        ink_box = _translated(base_box, x, y)
        layouts.append(MarkLayout(mark_id, role, x, y, ink_box))
    return tuple(layouts)


def _rhythm_line_count(event: Event) -> int:
    if event.kind == "extension":
        return 0
    duration = event.duration
    if event.tuplet_count:
        normal_count = event.tuplet_normal_count or tuplet_normal_notes(
            event.tuplet_count
        )
        if normal_count != event.tuplet_count:
            duration *= Fraction(event.tuplet_count, normal_count)
    count = 0
    unit = Fraction(1)
    while duration > 0 and duration < unit and count < 4:
        count += 1
        unit /= 2
    return count


def _rhythm_bottom_from_note_bottom(
    event: Event, note_bottom: float, style: PublicationStyle
) -> float:
    rhythm_lines = _rhythm_line_count(event)
    if not rhythm_lines:
        return note_bottom
    return (
        note_bottom
        + 12.5 * _chord_rhythm_scale(event, style)
        + (rhythm_lines - 1)
        * style.rhythm_line_level_step
        * _chord_rhythm_scale(event, style)
        + style.stroke_width * _chord_rhythm_scale(event, style)
    )


def _low_octave_first_center(
    event: Event,
    row_y: float,
    row_note_bottom: float,
    note_bottom: float,
    style: PublicationStyle,
) -> float:
    """Place low-octave dots below their note or the shared rhythm lines."""
    dot_scale = style.chord_octave_dot_scale if _chorded(event) else 1.0
    dot_radius = style.octave_dot_radius * dot_scale
    base = (
        _rhythm_bottom_from_note_bottom(event, note_bottom, style)
        if _rhythm_line_count(event)
        else row_note_bottom
    )
    if not _rhythm_line_count(event):
        return base + style.event_clearance + dot_radius
    return base - row_y + style.event_clearance + dot_radius


def _duration_extension_start(event: Event, style: PublicationStyle) -> float:
    scale = style.chord_rhythm_scale if _chorded(event) else 1.0
    if not event.dotted:
        return 17.0 * scale
    return (
        17.0 * scale
        + max(0, event.dotted - 1) * style.rhythm_dot_step * scale
        + style.rhythm_dot_radius * scale
        + style.duration_dot_clearance * scale
    )


def _event_attachment_bottom(event: Event, style: PublicationStyle) -> float:
    rows = pitch_layouts(event, style)
    note_bottom = max((row.note_box.bottom for row in rows), default=0.0)
    attachment_bottom = note_bottom
    for row in rows:
        for box in row.octave_boxes:
            attachment_bottom = max(attachment_bottom, box.bottom)
    rhythm_lines = _rhythm_line_count(event)
    if rhythm_lines:
        attachment_bottom = max(
            attachment_bottom,
            _rhythm_bottom_from_note_bottom(event, note_bottom, style),
        )
    return attachment_bottom


def _dynamic_baseline(event: Event, style: PublicationStyle) -> float:
    if not event.dynamic:
        return style.dynamic_baseline_floor
    _left, ink_top, _right, _bottom = font_registry().ink_bounds(
        event.dynamic, style.annotation_size
    )
    return max(
        style.dynamic_baseline_floor,
        _event_attachment_bottom(event, style) + style.dynamic_clearance - ink_top,
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


def measure_event_layout(
    event: Event, style: PublicationStyle, *, subtext_offset: float = 0.0
) -> EventLayout:
    """Measure every visible event component with one conservative geometry pass."""

    if event.kind == "extension":
        scale = style.chord_rhythm_scale if event.chorded_extension else 1.0
        box = InkBox(-5.5 * scale, -7.0 * scale, 5.5 * scale, -5.0 * scale)
        return EventLayout(box, (VisualPart("extension-line", box),))

    parts: list[VisualPart] = []
    pitch_rows = pitch_layouts(event, style)
    if pitch_rows:
        for row in pitch_rows:
            parts.append(VisualPart("note", row.note_box))
    else:
        parts.append(VisualPart("note", _centered_text_box("0", style.note_size, 500)))

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
            scale = _chord_rhythm_scale(event, style)
            right = left + ((extensions - 1) * style.extension_line_step + 11) * scale
            dash = InkBox(left, -7 * scale, right, -5 * scale)
            box = box.union(dash)
            parts.append(VisualPart("extension-line", dash))
    if event.dotted:
        scale = _chord_rhythm_scale(event, style)
        radius = style.rhythm_dot_radius * scale
        step = style.rhythm_dot_step * scale
        right = 17 * scale + (event.dotted - 1) * step + radius
        box = box.union(
            InkBox(
                17 * scale - radius,
                -7 * scale - radius,
                right,
                -7 * scale + radius,
            )
        )
        parts.append(
            VisualPart(
                "rhythm-dot",
                InkBox(
                    17 * scale - radius,
                    -7 * scale - radius,
                    right,
                    -7 * scale + radius,
                ),
            )
        )

    chord_bottom = max((row.note_box.bottom for row in pitch_rows), default=0.0)
    attachment_bottom = chord_bottom
    for row in pitch_rows:
        for dot_box in row.octave_boxes:
            attachment_bottom = max(attachment_bottom, dot_box.bottom)
    rhythm_lines = _rhythm_line_count(event)
    if rhythm_lines:
        rhythm_bottom = _rhythm_bottom_from_note_bottom(event, chord_bottom, style)
        # A rhythm line is a span shared across a run of events, not the ink of
        # a single event. Reserving its side extent as per-event horizontal width
        # would double-count the span and inflate the minimum gap between two
        # beamed notes; the horizontal floor comes from the digit ink plus
        # event_clearance instead. Only the vertical reservation is kept here so
        # lyrics, dynamics and low octave dots still clear the lines.
        box = InkBox(box.left, box.top, box.right, max(box.bottom, rhythm_bottom))
    if event.lyric:
        lyric_baseline = _lyric_baseline(event, style) + subtext_offset
        lyric_box = _translated(
            lyric_text_box(event.lyric, style.lyric_size, melisma=event.tie_start),
            0.0,
            lyric_baseline,
        )
        parts.append(VisualPart("lyric", lyric_box))
        box = box.union(lyric_box)
    # Other verses' lyrics are rendered as text blocks (not event lyric
    # parts), but their horizontal extent must still participate in
    # collision detection so that wide multi-verse lyrics (e.g. English
    # verse 2 alongside Chinese verse 1) get enough note spacing.
    for verse, text in (event.lyrics or {}).items():
        if verse == 1 or not text:
            continue
        box = box.union(lyric_text_box(text, style.lyric_size, melisma=event.tie_start))
    if event.dynamic:
        dynamic_baseline = _dynamic_baseline(event, style) + subtext_offset
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


def measure_event_ink(
    event: Event, style: PublicationStyle, *, subtext_offset: float = 0.0
) -> InkBox:
    return measure_event_layout(event, style, subtext_offset=subtext_offset).ink_box
