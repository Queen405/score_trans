from __future__ import annotations

from ..models.layout import RenderItem
from ..parsing.tokens import _parse_chord_token, _parse_note
from ..utils.geometry import _duration_line_y

BEAM_LINE_GAP = 6.0


def _render_beams(slots: list[tuple[RenderItem, float, float]], y: int) -> list[str]:
    out: list[str] = []
    parent_runs: list[tuple[int, int, float]] = []
    for level in range(1, 4):
        current_runs: list[tuple[int, int, float]] = []
        for start_index, end_index, run in _beam_runs(slots, level):
            beam_y = _beam_run_y(run, y, level)
            parent_y = _parent_beam_y(parent_runs, start_index, end_index)
            if parent_y is not None:
                beam_y = max(beam_y, parent_y + BEAM_LINE_GAP)
            out.extend(_render_beam_run(run, beam_y))
            current_runs.append((start_index, end_index, beam_y))
        parent_runs = current_runs
    return out


def _beam_runs(
    slots: list[tuple[RenderItem, float, float]], level: int
) -> list[tuple[int, int, list[tuple[RenderItem, float, float]]]]:
    runs: list[tuple[int, int, list[tuple[RenderItem, float, float]]]] = []
    run: list[tuple[RenderItem, float, float]] = []
    start_index = 0
    for index, slot in enumerate(slots):
        item, _, _ = slot
        if _beamable_slashes(item.token) >= level:
            if not run:
                start_index = index
            run.append(slot)
        else:
            if run:
                runs.append((start_index, index - 1, run))
            run = []
    if run:
        runs.append((start_index, len(slots) - 1, run))
    return runs


def _render_beam_run(
    run: list[tuple[RenderItem, float, float]], beam_y: float
) -> list[str]:
    if not run:
        return []
    first_item, first_cx, _ = run[0]
    last_item, last_cx, _ = run[-1]
    start = first_cx - _beam_half_width(first_item.token)
    end = last_cx + _beam_half_width(last_item.token)
    return [
        f'<line class="duration-line beam-line" x1="{start:.1f}" y1="{beam_y:.1f}" x2="{end:.1f}" y2="{beam_y:.1f}"/>'
    ]


def _beam_run_y(
    run: list[tuple[RenderItem, float, float]], y: int, level: int
) -> float:
    return max(_beam_y(item.token, y, level) for item, _, _ in run)


def _parent_beam_y(
    parent_runs: list[tuple[int, int, float]], start_index: int, end_index: int
) -> float | None:
    for parent_start, parent_end, parent_y in parent_runs:
        if parent_start <= start_index and end_index <= parent_end:
            return parent_y
    return None


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
