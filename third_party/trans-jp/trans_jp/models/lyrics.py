from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from .geometry import Box

LYRICS_VERSION = 4
SUPPORTED_LYRICS_VERSIONS = (3, 4)


@dataclass(frozen=True, slots=True)
class TextRegion:
    region_id: str
    bounds_work: Box
    bounds: Box


@dataclass(slots=True)
class LyricToken:
    token_id: str
    text: str
    bounds: Box
    bounds_work: Box
    granularity: str
    recognition_status: str = "observed"
    localization_status: str = "unresolved"
    confidence: float | None = None
    candidate_note_ids: tuple[str, ...] = ()
    alignment_status: str = "unconfirmed"


@dataclass(slots=True)
class LyricLine:
    region_id: str
    text: str
    bounds: Box
    bounds_work: Box
    language: str
    tokens: list[LyricToken] = field(default_factory=list)
    recognition_status: str = "observed"
    localization_status: str = "line_only"
    associated_region_id: str | None = None
    verse_index: int | None = None


@dataclass(slots=True)
class LyricsResult:
    version: int = LYRICS_VERSION
    lines: list[LyricLine] = field(default_factory=list)
    regions: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)
    refinement: list[dict] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TextRequest:
    request_id: str
    image_path: Path
    items: tuple[dict, ...]
    task: str
    sha256: str
