from __future__ import annotations

from ..constants import CHORD_GAP
from ..models.shapes import NoteShape
from ..parsing.tokens import _parse_chord_token, _parse_note


def _token_metrics(token: str, y: int) -> dict[str, float]:
    token = token.strip().strip("()~")
    chord = _parse_chord_token(token)
    if chord is not None:
        notes, slashes, _dotted, extension = chord
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


def _low_octave_dot_y(y: int, index: int) -> float:
    from ..constants import LOW_OCTAVE_DOT_OFFSET, OCTAVE_DOT_GAP
    return y + LOW_OCTAVE_DOT_OFFSET + index * OCTAVE_DOT_GAP


def _note_duration_line_y(note: NoteShape, y: int, level: int) -> float:
    base = y + 10
    if note.octave_down:
        base = max(base, _low_octave_dot_y(y, note.octave_down - 1) + 12)
    return base + (level - 1) * 6
