from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from .candidates import CandidateRegistry

BATCH_SIZE = 12
CLASSIFIER_VERSION = 1


@dataclass(frozen=True, slots=True)
class CandidateBatchRequest:
    batch_id: str
    image_path: Path
    atlas_path: Path
    registry: CandidateRegistry
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateClassification:
    candidate_id: str
    label: str = "unknown"
    kind: str = "unknown"
    confidence: float | None = None
    status: str = "candidate_unresolved"
    reason: str = ""


@dataclass(slots=True)
class CandidateBatchResult:
    batch_id: str
    registry_sha256: str
    items: list[CandidateClassification] = field(default_factory=list)
    status: str = "classified"
    raw_response: str = ""
    warnings: list[str] = field(default_factory=list)
    finish_reason: str | None = None
