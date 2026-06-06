from __future__ import annotations

from ..constants import CHORD_GAP
from ..models.shapes import NoteShape
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.geometry import _duration_line_y
from ..utils.helpers import _split_accidental
from ..utils.text import _esc
from ..utils.metrics import _high_octave_dot_y, _low_octave_dot_y, _note_center_offset, _note_duration_line_y, _note_visual_bottom, _note_visual_top


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
    note_positions = [(note, int(top_y + index * gap)) for index, note in enumerate(notes)]
    out: list[str] = []
    for note, note_y in note_positions:
        dot_cx = cx + _note_center_offset(note) - 4
        upper_bound = None
        lower_bound = None
        for neighbor, neighbor_y in note_positions:
            if neighbor is note:
                continue
            if neighbor.rank > note.rank:
                upper_bound = (
                    _note_visual_bottom(neighbor, neighbor_y, include_duration=False)
                    if upper_bound is None
                    else max(upper_bound, _note_visual_bottom(neighbor, neighbor_y, include_duration=False))
                )
            elif neighbor.rank < note.rank:
                lower_bound = (
                    _note_visual_top(neighbor, neighbor_y)
                    if lower_bound is None
                    else min(lower_bound, _note_visual_top(neighbor, neighbor_y))
                )
        out.extend(_render_note_shape(note, cx, note_y, generated=generated, suppress_duration=True, dot_cx=dot_cx, upper_bound=upper_bound, lower_bound=lower_bound))
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
    dot_cx: float | None = None,
    upper_bound: float | None = None,
    lower_bound: float | None = None,
) -> list[str]:
    note_class = "note generated" if generated else "note"
    accidental, body = _split_accidental(note.display)
    note_x = cx + (2 if accidental else 0)
    dot_x = dot_cx if dot_cx is not None else cx
    out: list[str] = []
    if accidental:
        out.append(f'<text class="accidental" x="{cx - 12:.1f}" y="{y - 14}" text-anchor="middle">{_esc(accidental)}</text>')
    out.append(f'<text class="{note_class}" x="{note_x:.1f}" y="{y}" text-anchor="middle">{_esc(body)}</text>')
    if not suppress_duration:
        for line in range(min(3, note.slashes)):
            line_y = _note_duration_line_y(note, y, line + 1)
            out.append(
                f'<line class="duration-line" x1="{cx - 13:.1f}" y1="{line_y:.1f}" '
                f'x2="{cx + 13:.1f}" y2="{line_y:.1f}"/>'
            )
    dot_spacing = 8  # horizontal gap between octave dots
    for dot in range(min(3, note.octave_up)):
        dot_y = _high_octave_dot_y(y, dot, upper_bound)
        this_dot_x = dot_x + (dot - (note.octave_up - 1) / 2) * dot_spacing
        out.append(f'<circle class="octave-dot" cx="{this_dot_x:.1f}" cy="{dot_y:.1f}" r="2.2"/>')
    for dot in range(min(3, note.octave_down)):
        dot_y = _low_octave_dot_y(y, dot, lower_bound)
        this_dot_x = dot_x + (dot - (note.octave_down - 1) / 2) * dot_spacing
        out.append(f'<circle class="octave-dot" cx="{this_dot_x:.1f}" cy="{dot_y:.1f}" r="2.2"/>')
    if note.dotted:
        out.append(f'<circle class="rhythm-dot" cx="{cx + 20:.1f}" cy="{y - 8}" r="3.0"/>')
    if not suppress_duration:
        for mark in range(min(3, note.extension)):
            start = cx + 20 + mark * 32
            out.append(f'<line class="extension-line" x1="{start:.1f}" y1="{y - 9:.1f}" x2="{start + 30:.1f}" y2="{y - 9:.1f}"/>')
    return out
