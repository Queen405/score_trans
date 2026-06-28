from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from .common.types import InstrumentProfile


TextRole = Literal[
    "title", "instrument", "lyric", "expression", "footer", "measure_number", "other"
]
EventKind = Literal["note", "rest"]


@dataclass(slots=True)
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float] | None = None
    confidence: float | None = None
    role: TextRole = "other"
    font_size: float | None = None
    measure_number: str | int | None = None
    start: Fraction | None = None
    placement: str | None = None
    staff: str | None = None


@dataclass(slots=True)
class JianpuPitch:
    degree: int
    octave: int = 0
    accidental: int = 0
    midi: int | None = None
    step: str | None = None
    alter: int = 0
    accidental_text: str | None = None

    @property
    def rank(self) -> float:
        return self.octave * 10 + self.degree + self.accidental * 0.1


@dataclass(slots=True)
class Event:
    kind: EventKind
    duration: Fraction
    pitches: list[JianpuPitch] = field(default_factory=list)
    dotted: int = 0
    tie_start: bool = False
    tie_stop: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    slide_start: bool = False
    slide_stop: bool = False
    lyric: str | None = None
    dynamic: str | None = None
    articulation: str | None = None
    articulations: list[str] = field(default_factory=list)
    ornaments: list[str] = field(default_factory=list)
    technical: list[str] = field(default_factory=list)
    voice: str | None = None
    staff: str | None = None
    start: Fraction | None = None
    generated: bool = False
    source_token: str | None = None
    tuplet_id: str | None = None
    tuplet_count: int | None = None
    tuplet_index: int | None = None
    tuplet_start: bool = False
    tuplet_stop: bool = False

    @property
    def is_chord(self) -> bool:
        return len(self.pitches) > 1


@dataclass(slots=True)
class Beat:
    index: int
    duration: Fraction
    start: Fraction = Fraction(0, 1)
    events: list[Event] = field(default_factory=list)


@dataclass(slots=True, init=False)
class Measure:
    source_number: str
    display_measure_number: str | int
    duration: Fraction
    beats: list[Beat] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    text_blocks: list[TextBlock] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    beats_per_measure: int = 4
    beat_type: int = 4
    source_key: str = "C"
    target_key: str = "C"
    repeat_start: bool = False
    repeat_end: bool = False
    repeat_count: int = 1
    source_page_index: int | None = None

    def __init__(
        self,
        source_number: str,
        display_measure_number: str | int | None = None,
        duration: Fraction = Fraction(0, 1),
        beats: list[Beat] | None = None,
        events: list[Event] | None = None,
        text_blocks: list[TextBlock] | None = None,
        validation_errors: list[str] | None = None,
        beats_per_measure: int = 4,
        beat_type: int = 4,
        source_key: str = "C",
        target_key: str = "C",
        repeat_start: bool = False,
        repeat_end: bool = False,
        display_number: str | int | None = None,
        repeat_count: int = 1,
        source_page_index: int | None = None,
    ) -> None:
        if display_measure_number is None:
            display_measure_number = (
                display_number if display_number is not None else source_number
            )
        self.source_number = source_number
        self.display_measure_number = display_measure_number
        self.duration = duration
        self.beats = beats if beats is not None else []
        self.events = events if events is not None else []
        self.text_blocks = text_blocks if text_blocks is not None else []
        self.validation_errors = (
            validation_errors if validation_errors is not None else []
        )
        self.beats_per_measure = beats_per_measure
        self.beat_type = beat_type
        self.source_key = source_key
        self.target_key = target_key
        self.repeat_start = repeat_start
        self.repeat_end = repeat_end
        self.repeat_count = repeat_count
        self.source_page_index = source_page_index

    @property
    def display_number(self) -> str | int:
        return self.display_measure_number

    @display_number.setter
    def display_number(self, value: str | int) -> None:
        self.display_measure_number = value

    @property
    def total_duration(self) -> Fraction:
        return sum((event.duration for event in self.events), Fraction(0, 1))

    @property
    def span_duration(self) -> Fraction:
        ends = (
            (event.start or Fraction(0, 1)) + event.duration for event in self.events
        )
        return max(ends, default=Fraction(0, 1))

    @property
    def overflow_duration(self) -> Fraction:
        return max(Fraction(0, 1), self.span_duration - self.duration)


@dataclass(slots=True)
class JianpuScore:
    title: str = "简谱"
    target_key: str = "C"
    source_key: str = "C"
    beats: int = 4
    beat_type: int = 4
    instrument_profile: InstrumentProfile = "general"
    measures: list[Measure] = field(default_factory=list)
    text_blocks: list[TextBlock] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)

    @property
    def measure_duration(self) -> Fraction:
        return Fraction(self.beats * 4, self.beat_type)

    @property
    def beat_duration(self) -> Fraction:
        return Fraction(4, self.beat_type)


JianpuEvent = Event
JianpuBeat = Beat
JianpuMeasure = Measure
OCRTextBlock = TextBlock
