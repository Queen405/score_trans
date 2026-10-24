from __future__ import annotations

from pydantic import BaseModel, Field

from ..common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    TargetKeyOrAuto,
)
from ..provenance.schemas import SourceTextAttachment, TextAnchor
from ..render.layout import A4LayoutRequest


class CorrectableEntityDTO(BaseModel):
    source_id: str
    inter_id: str
    sheet_index: int
    tag: str
    shape: str
    grade: float
    bounds_x: float
    bounds_y: float
    bounds_w: float
    bounds_h: float
    is_structural: bool
    musicxml_locator: str | None = None
    hit_path: str | None = None
    candidates: list["CandidateDTO"] = Field(default_factory=list)
    current_score_kind: str = "audiveris_inter_grade"
    can_delete: bool = True


class CandidateDTO(BaseModel):
    shape: str
    score: float
    score_kind: str


class SuspiciousGlyphDTO(BaseModel):
    glyph_id: str
    bounds_x: float
    bounds_y: float
    bounds_w: float
    bounds_h: float
    hit_path: str
    candidates: list[CandidateDTO] = Field(default_factory=list)
    tag: str = "unrecognized-head"
    shape: str = "UNKNOWN"
    grade: float = 0.0
    inter_id: str | None = None
    staff: str | None = None
    pitch: float | None = None


class SheetEntitiesDTO(BaseModel):
    sheet_index: int
    width: int
    height: int
    entities: list[CorrectableEntityDTO] = Field(default_factory=list)
    suspicious_glyphs: list[SuspiciousGlyphDTO] = Field(default_factory=list)


class EntitiesResponse(BaseModel):
    sheets: list[SheetEntitiesDTO] = Field(default_factory=list)


class ConversionOptionsDTO(A4LayoutRequest):
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile = "general"
    show_measure_numbers: bool = True
    measure_number_mode: MeasureNumberMode = "all"
    title: str | None = None


class CorrectionRequest(BaseModel):
    original_musicxml: str
    omr_file_id: str
    source_map_file_id: str
    deleted_source_ids: list[str] = Field(min_length=0)
    candidate_selections: dict[str, str] = Field(default_factory=dict)
    text_attachments: list[SourceTextAttachment] = Field(default_factory=list)
    options: ConversionOptionsDTO = Field(default_factory=ConversionOptionsDTO)


class CorrectionResponse(BaseModel):
    working_musicxml: str
    jianpu_text: str
    text_anchors: list[TextAnchor] = Field(default_factory=list)
    text_hash: str
    svg_file_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    applied_candidate_selections: dict[str, str] = Field(default_factory=dict)
