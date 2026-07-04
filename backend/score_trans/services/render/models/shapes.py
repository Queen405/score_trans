from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NoteShape:
    display: str
    slashes: int
    octave_up: int
    octave_down: int
    rank: float
    dotted: int = 0
    extension: int = 0
