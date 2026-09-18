from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from .geometry import Box
from .raster import Filament

CANDIDATE_VERSION = 3


@dataclass(frozen=True, slots=True)
class LocatedCandidate:
    candidate_id: str
    kind: str
    bounds: Box
    band_ids: tuple[int, ...]
    component_ids: tuple[str, ...]
    conflicts: tuple[str, ...] = ()
    ambiguous: bool = False
    lines: tuple[Filament, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateRegistry:
    row_index: int
    width: int
    height: int
    candidates: tuple[LocatedCandidate, ...]
    algorithm_version: int = CANDIDATE_VERSION

    @property
    def digest(self) -> str:
        payload = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RowRecognitionRequest:
    image_path: Path
    atlas_paths: tuple[Path, ...]
    registry: CandidateRegistry
    expected_schema: int = 2
