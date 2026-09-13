from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class MeasureVisit:
    source_index: int
    performance_start: Fraction
    score_start: Fraction
    duration: Fraction


@dataclass(slots=True)
class PlaybackTextSource:
    text_hash: str
    # Event object identities from the parsed scores; never serialized.
    event_ranges: dict[int, tuple[int, int]] = field(default_factory=dict)
