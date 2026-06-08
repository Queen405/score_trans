from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


class VisionPageResult(BaseModel):
    title: str | None = None
    key: str | None = None
    meter: str | None = None
    tempo: str | None = None
    jianpu_text: str
    measure_number_candidates: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)


@dataclass(slots=True)
class PreparedScorePage:
    page_index: int
    image_path: Path
    generated: bool = False


@dataclass(slots=True)
class TranscribedScorePage:
    prepared: PreparedScorePage
    result: VisionPageResult
    jianpu_text: str
    measure_number_candidates: list[int]
    validation_errors: list[str]


@dataclass(slots=True)
class AiTranscriptionResult:
    source_path: Path
    pages: list[TranscribedScorePage]
    merged_jianpu_text: str
    warnings: list[str]
