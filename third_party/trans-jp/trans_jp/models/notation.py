from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Pitch:
    degree: str
    octave: int = 0
    accidental: str = ""

    @property
    def order(self) -> int:
        return int(self.degree) + 7 * self.octave


@dataclass(frozen=True, slots=True)
class Notation:
    kind: str
    pitches: tuple[Pitch, ...] = ()
    underlines: int = 0
    dots: int = 0
    extensions: int = 0
    duration: Fraction = Fraction(0)
    opens: int = 0
    closes: int = 0
    tie_start: bool = False
    tie_end: bool = False
