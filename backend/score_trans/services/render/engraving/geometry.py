from __future__ import annotations

from dataclasses import dataclass
import math

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

    def union(self, other: "InkBox") -> "InkBox":
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


def _empty_box() -> InkBox:
    return InkBox(0.0, 0.0, 0.0, 0.0)


def _centered_text_box(value: str, size: float) -> InkBox:
    registry = font_registry()
    left, top, right, bottom = registry.ink_bounds(value, size)
    advance = registry.measure(value, size)
    return InkBox(left - advance / 2, top, right - advance / 2, bottom)


def _translated(box: InkBox, x: float, y: float) -> InkBox:
    return InkBox(box.left + x, box.top + y, box.right + x, box.bottom + y)


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
    }.get(renderer, mark_id)


def _rhythm_line_count(event: Event) -> int:
    duration = event.duration
    count = 0
    unit = 1
    while duration > 0 and duration < unit and count < 4:
        count += 1
        unit /= 2
    return count


def _is_tuplet(event: Event) -> bool:
    return bool(event.tuplet_id or event.tuplet_count or event.tuplet_spans)


def measure_event_layout(event: Event, style: PublicationStyle) -> EventLayout:
    """Measure every visible event component with one conservative geometry pass."""

    parts: list[VisualPart] = []
    pitches = event.pitches or [None]
    chord_gap = style.chord_gap
    chord_top = -(len(pitches) - 1) * chord_gap / 2
    note_boxes: list[InkBox] = []
    note_widths: list[float] = []
    for pitch in pitches:
        value = "0" if pitch is None else str(max(0, min(7, pitch.degree)))
        note_box = _translated(
            _centered_text_box(value, style.note_size),
            0.0,
            chord_top + len(note_boxes) * chord_gap,
        )
        note_boxes.append(note_box)
        note_widths.append(font_registry().measure(value, style.note_size))
    for note_box in note_boxes:
        parts.append(VisualPart("note", note_box))

    box = _empty_box()
    for part in parts:
        box = box.union(part.ink_box)

    note_width = max(note_widths, default=0.0)
    for index, pitch in enumerate(event.pitches):
        accidental = _accidental_text(pitch)
        if accidental:
            accidental_width = font_registry().measure(
                accidental, style.accidental_size
            )
            x = -note_width / 2 - accidental_width / 2 - style.accidental_clearance
            accidental_box = _translated(
                _centered_text_box(accidental, style.accidental_size),
                x,
                chord_top + index * chord_gap,
            )
            parts.append(VisualPart("accidental", accidental_box))
            box = box.union(accidental_box)

    for index, pitch in enumerate(event.pitches):
        if not pitch.octave:
            continue
        pitch_y = chord_top + index * chord_gap
        direction = -1 if pitch.octave > 0 else 1
        base_y = pitch_y - 21 if direction < 0 else pitch_y + 10
        for dot_index in range(abs(pitch.octave)):
            cy = base_y + direction * dot_index * 7
            radius = style.octave_dot_radius
            dot_box = InkBox(-radius, cy - radius, radius, cy + radius)
            parts.append(VisualPart("octave-dot", dot_box))
            box = box.union(dot_box)

    if event.duration > 1:
        extensions = max(0, int(math.ceil(float(event.duration))) - 1)
        if extensions:
            right = 17 + (extensions - 1) * style.extension_line_step + 11
            box = box.union(InkBox(17, -7, right, -5))
            parts.append(VisualPart("extension-line", InkBox(17, -7, right, -5)))
    if event.dotted:
        right = 17 + (event.dotted - 1) * style.rhythm_dot_step + style.rhythm_dot_radius
        box = box.union(
            InkBox(17 - style.rhythm_dot_radius, -7 - style.rhythm_dot_radius, right, -7 + style.rhythm_dot_radius)
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

    chord_half = max(0, len(event.pitches) - 1) * chord_gap / 2
    if not _is_tuplet(event):
        rhythm_lines = _rhythm_line_count(event)
        if rhythm_lines:
            box = box.union(
                InkBox(
                    -12,
                    chord_half + 13,
                    12,
                    chord_half + 13 + (rhythm_lines - 1) * 6 + style.stroke_width,
                )
            )
    if event.lyric:
        lyric_box = _translated(
            _centered_text_box(event.lyric, style.lyric_size), 0.0, 44.0
        )
        parts.append(VisualPart("lyric", lyric_box))
        box = box.union(lyric_box)
    if event.dynamic:
        dynamic_box = _translated(
            _centered_text_box(event.dynamic, style.annotation_size), 0.0, 63.0
        )
        parts.append(VisualPart("dynamic", dynamic_box))
        box = box.union(dynamic_box)

    mark_ids = list(dict.fromkeys([*event.articulations, *event.ornaments, *event.technical]))
    if event.articulation and event.articulation not in mark_ids:
        mark_ids.insert(0, event.articulation)
    for index, mark_id in enumerate(mark_ids):
        spec = get_performance_mark(mark_id)
        placement = spec.placement if spec else "above"
        if mark_id == "staccato":
            radius = style.staccato_radius
            mark_box = InkBox(-radius, -35 - radius, radius, -35 + radius)
        else:
            label = _mark_label(mark_id)
            mark_box = _translated(
                _centered_text_box(label, style.annotation_size),
                0.0,
                -35.0 - index * 16.0,
            )
            if placement == "left":
                mark_box = _translated(mark_box, -24.0, 37.0)
            elif placement == "right":
                mark_box = _translated(mark_box, 24.0, 37.0)
            elif placement == "below-right":
                mark_box = _translated(mark_box, 22.0, 55.0)
        parts.append(VisualPart("mark", mark_box))
        box = box.union(mark_box)
    return EventLayout(box, tuple(parts))


def measure_event_ink(event: Event, style: PublicationStyle) -> InkBox:
    return measure_event_layout(event, style).ink_box
