from __future__ import annotations

from ..constants import CHORD_GAP
from ..models.shapes import NoteShape
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.geometry import _duration_line_y
from ..utils.helpers import _split_accidental
from ..utils.text import _esc
from ..utils.metrics import _low_octave_dot_y, _note_duration_line_y


def _render_token(
    token: str,
    cx: float,
    y: int,
    *,
    generated: bool = False,
    suppress_duration: bool = False,
) -> list[str]:
    token = token.strip().strip("()~")
    if token == "-":
        return [f'<line class="extension-line" x1="{cx - 10:.1f}" y1="{y - 9:.1f}" x2="{cx + 10:.1f}" y2="{y - 9:.1f}"/>']
    if _parse_chord_token(token) is not None:
        out = _render_chord(token, cx, y, generated=generated, suppress_duration=suppress_duration)
    else:
        out = _render_note_shape(_parse_note(token), cx, y, generated=generated, suppress_duration=suppress_duration)
    return out


def _render_chord(
    token: str,
    cx: float,
    y: int,
    *,
    generated: bool = False,
    suppress_duration: bool = False,
) -> list[str]:
    chord = _parse_chord_token(token)
    if chord is None:
        return []
    notes, slashes, dotted, extension = chord
    notes = sorted(notes, key=lambda note: note.rank, reverse=True)
    if not notes:
        return []
    gap = CHORD_GAP
    top_y = y - (len(notes) - 1) * gap / 2
    out: list[str] = []
    for index, note in enumerate(notes):
        out.extend(_render_note_shape(note, cx, int(top_y + index * gap), generated=generated, suppress_duration=True))
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
        start = cx + 22 + mark * 32
        out.append(f'<line class="extension-line" x1="{start:.1f}" y1="{y - 9:.1f}" x2="{start + 30:.1f}" y2="{y - 9:.1f}"/>')
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
            start = cx + 20 + mark * 32
            out.append(f'<line class="extension-line" x1="{start:.1f}" y1="{y - 9:.1f}" x2="{start + 30:.1f}" y2="{y - 9:.1f}"/>')
    return out
