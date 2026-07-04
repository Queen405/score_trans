from __future__ import annotations

from fractions import Fraction
import re

from ....domain.jianpu_tokens import (
    PREFIX_SLASHES,
    consume_duration_prefix,
    consume_duration_suffix,
    duration_prefix,
)
from ..models.shapes import NoteShape


def _parse_note(token: str) -> NoteShape:
    token = token.strip().strip("()~")
    prefix = duration_prefix(token)
    base_duration, token = consume_duration_prefix(token)
    slashes = PREFIX_SLASHES.get(prefix, 0)
    extension = len(token) - len(token.rstrip("-"))
    _duration, token, dotted = consume_duration_suffix(base_duration, token)
    octave_up = token.count("'")
    octave_down = token.count(",")
    display = token.replace("'", "").replace(",", "")
    display = re.sub(
        r"((?:tqf|tqs|qf|qs|bb|[#bnx♮])?[0-7])[-]*$",
        r"\1",
        display,
    )
    degree_match = re.search(r"([0-7])", display)
    degree = int(degree_match.group(1)) if degree_match else 0
    accidental = (
        0.2
        if display.startswith("x")
        else 0.15
        if display.startswith("tqs")
        else 0.05
        if display.startswith("qs")
        else 0.1
        if "#" in display
        else -0.2
        if display.startswith("bb")
        else -0.15
        if display.startswith("tqf")
        else -0.05
        if display.startswith("qf")
        else -0.1
        if "b" in display
        else 0
    )
    return NoteShape(
        display=display,
        slashes=slashes,
        octave_up=octave_up,
        octave_down=octave_down,
        rank=(octave_up - octave_down) * 10 + degree + accidental,
        dotted=dotted,
        extension=extension,
    )


def _parse_chord_token(token: str) -> tuple[list[NoteShape], int, int, int] | None:
    token = token.strip().strip("()~")
    prefix = duration_prefix(token)
    base_duration, work = consume_duration_prefix(token)
    extension = len(work) - len(work.rstrip("-"))
    _duration, work, dotted = consume_duration_suffix(base_duration, work)
    if not (work.startswith("[") and work.endswith("]")):
        return None
    notes = [
        _parse_note(part.strip()) for part in work[1:-1].split("+") if part.strip()
    ]
    slashes = max(
        [PREFIX_SLASHES.get(prefix, 0), *(note.slashes for note in notes)], default=0
    )
    return notes, slashes, dotted, extension


def _token_slashes(token: str) -> int:
    chord = _parse_chord_token(token)
    if chord is not None:
        _notes, slashes, _dotted, _extension = chord
        return slashes
    return _parse_note(token).slashes


def _token_duration(token: str) -> Fraction:
    from ....domain.jianpu_tokens import token_duration as _td

    return _td(token)
