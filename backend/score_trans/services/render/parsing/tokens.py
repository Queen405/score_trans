from __future__ import annotations

from fractions import Fraction
import re

from ....domain.jianpu_tokens import PREFIX_SLASHES, consume_duration_prefix
from ..models.shapes import NoteShape


def _parse_note(token: str) -> NoteShape:
    token = token.strip().strip("()~")
    prefix = token[0] if token and token[0] in PREFIX_SLASHES and token[0] else ""
    _duration, token = consume_duration_prefix(token)
    slashes = PREFIX_SLASHES.get(prefix, 0)
    octave_up = token.count("'")
    octave_down = token.count(",")
    dotted = "." in token
    extension_match = re.search(r"(-*)$", token)
    extension = len(extension_match.group(1)) if extension_match else 0
    display = token.replace("'", "").replace(",", "").replace(".", "")
    display = re.sub(r"((?:bb|[#bnx♮])?[0-7])[-]*$", r"\1", display)
    degree_match = re.search(r"([0-7])", display)
    degree = int(degree_match.group(1)) if degree_match else 0
    accidental = 0.2 if display.startswith("x") else 0.1 if "#" in display else -0.2 if display.startswith("bb") else -0.1 if "b" in display else 0
    return NoteShape(
        display=display,
        slashes=slashes,
        octave_up=octave_up,
        octave_down=octave_down,
        rank=(octave_up - octave_down) * 10 + degree + accidental,
        dotted=dotted,
        extension=extension,
    )


def _parse_chord_token(token: str) -> tuple[list[NoteShape], int, bool, int] | None:
    token = token.strip().strip("()~")
    prefix = token[0] if token and token[0] in PREFIX_SLASHES and token[0] else ""
    _duration, work = consume_duration_prefix(token)
    extension_match = re.search(r"(-*)$", work)
    extension = len(extension_match.group(1)) if extension_match else 0
    work = work.rstrip("-")
    dotted = work.endswith(".")
    if dotted:
        work = work[:-1]
    if not (work.startswith("[") and work.endswith("]")):
        return None
    notes = [_parse_note(part.strip()) for part in work[1:-1].split("+") if part.strip()]
    slashes = max([PREFIX_SLASHES.get(prefix, 0), *(note.slashes for note in notes)], default=0)
    return notes, slashes, dotted, extension


def _token_duration(token: str) -> Fraction:
    from ....domain.jianpu_tokens import token_duration as _td
    return _td(token)
