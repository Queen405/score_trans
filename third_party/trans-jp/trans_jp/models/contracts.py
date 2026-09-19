from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .geometry import TokenGeometry, Transform
from .raster import RowAnalysis
from .candidates import CandidateRegistry

DEFAULT_SHEET_INDEX = 0


def make_source_id(
    row_index: int, token_index: int, sheet_index: int = DEFAULT_SHEET_INDEX
) -> str:
    return f"s{sheet_index}:r{row_index}:t{token_index}"


@dataclass(slots=True)
class RowSegment:
    index: int
    y_top: int
    y_bottom: int
    image_path: Path
    width: int
    height: int
    work_y_top: int = 0
    transform: Transform = field(default_factory=Transform)


@dataclass(slots=True)
class RecognizedToken:
    index: int
    text: str
    x: float | None
    w: float | None
    role: str
    y: float | None = None
    h: float | None = None
    geometry: TokenGeometry | None = None
    candidate_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class RowResult:
    row: RowSegment
    row_type: str
    jianpu_text: str
    tokens: list[RecognizedToken]
    key: str | None = None
    meter: str | None = None
    tempo: str | int | None = None
    title: str | None = None
    warnings: list[str] = field(default_factory=list)
    confidence: float | None = None
    analysis: RowAnalysis | None = None
    schema_version: int = 1
    registry: CandidateRegistry | None = None
    unresolved_candidates: list[dict] = field(default_factory=list)
    raw_response: str | None = None
    complete: bool = True
    recognition_scope: str = "full_notation"
    batch_diagnostics: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class TransJpResult:
    jianpu_text: str
    rows: list[RowResult]
    source_map: dict
    overlay_svg: str
    text_anchors: list[dict]
    warnings: list[str] = field(default_factory=list)

    input_path: Path | None = None
    debug: bool = False
    diagnostics: dict = field(default_factory=dict)
    preview_png: bytes = b""
    debug_svg: str = ""
    melody: dict = field(default_factory=dict)
    lyrics: dict = field(default_factory=dict)
    lyrics_svg: str = ""
    pending_svg: str = ""
    lyrics_preview_html: str = ""


@dataclass(slots=True)
class LlmConfig:
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.1
    timeout: float = 120.0


@dataclass(slots=True)
class CliConfig:
    input_path: Path
    output_dir: Path
    llm: LlmConfig
    target_key: str = "C"
    title: str | None = None
    extra_prompt: str | None = None
    prompt_config: Path | None = None
    concurrency: int = 2
    min_image_edge: int = 2500
    debug: bool = False
    recognition_mode: str = "bodies"
    body_responses_dir: Path | None = None
    melody_review: bool = True
    lyrics_mode: str = "off"
    lyrics_refine: bool = False
    lyrics_responses_dir: Path | None = None
    lyrics_ocr: LlmConfig | None = None


@dataclass(slots=True)
class CompletionResult:
    content: str
    finish_reason: str | None = None
