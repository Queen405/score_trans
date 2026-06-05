from __future__ import annotations

from ..models.layout import RenderItem
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.geometry import _duration_line_y


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
    chord = _parse_chord_token(token)
    if chord is not None:
        _notes, slashes, _dotted, _extension = chord
        return slashes
    note = _parse_note(token)
    return note.slashes


def _beam_half_width(token: str) -> float:
    token = token.strip().strip("()~")
    return 18.0 if _parse_chord_token(token) is not None else 15.0


def _beam_y(token: str, y: int, level: int) -> float:
    return _duration_line_y(token, y, level)
