from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from .geometry import Box
from .raster import Filament

MELODY_VERSION = 1
ATTACHMENT_VERSION = 1


@dataclass(frozen=True, slots=True)
class AttachmentCandidate:
    candidate_id: str
    bounds: Box
    kinds: tuple[str, ...]
    component_ids: tuple[str, ...]
    owners: tuple[str, ...]
    line: Filament | None = None


@dataclass(frozen=True, slots=True)
class AttachmentRelation:
    candidate_id: str
    body_ids: tuple[str, ...]
    kind: str
    status: str = "confirmed"
    source: str = "cv"


@dataclass(slots=True)
class AttributeValue:
    value: int | str | None
    status: str
    evidence_ids: tuple[str, ...] = ()
    source: str = "cv"
    reason: str = ""


@dataclass(slots=True)
class NoteAttributes:
    body_id: str
    source_id: str
    degree: str
    fields: dict[str, AttributeValue]
    duration: Fraction | None = None
    complete: bool = False
    effective_accidental: AttributeValue = field(
        default_factory=lambda: AttributeValue(
            None, "unknown", reason="小节及调号状态未确认"
        )
    )


@dataclass(slots=True)
class MelodyRegionResult:
    region_id: str
    status: str
    notes: list[NoteAttributes] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    text: str | None = None
    measure_duration: Fraction | None = None
    meter_status: str = "unknown"


@dataclass(frozen=True, slots=True)
class AttachmentReviewRequest:
    request_id: str
    image_path: Path
    body_ids: tuple[str, ...]
    candidates: tuple[AttachmentCandidate, ...]
    payload_sha256: str


@dataclass(slots=True)
class AttachmentReviewResult:
    request_id: str
    relations: list[AttachmentRelation] = field(default_factory=list)
    unknown_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    status: str = "reviewed"
    raw_response: str = ""
    reason: str = ""
    finish_reason: str | None = None
