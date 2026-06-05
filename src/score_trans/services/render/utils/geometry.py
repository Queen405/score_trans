from __future__ import annotations

from ..constants import CHORD_GAP
from ..models.shapes import NoteShape
from ..parsing.tokens import _parse_chord_token, _parse_note
from .metrics import _note_visual_bottom, _note_visual_top


def _duration_line_y(token: str, y: int, level: int) -> float:
    token = token.strip().strip("()~")
    chord = _parse_chord_token(token)
    if chord is not None:
        notes, _slashes, _dotted, _extension = chord
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
        from .metrics import _low_octave_dot_y
        base = max(base, _low_octave_dot_y(y, note.octave_down - 1) + 12)
    return base + (level - 1) * 6
