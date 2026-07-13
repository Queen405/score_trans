from __future__ import annotations

from pydantic import BaseModel


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


class SheetEntitiesDTO(BaseModel):
    sheet_index: int
    width: int
    height: int
    entities: list[CorrectableEntityDTO] = []


class EntitiesResponse(BaseModel):
    sheets: list[SheetEntitiesDTO] = []


class ConversionOptionsDTO(BaseModel):
    target_key: str = "C"
    accidental_mode: str = "auto"
    instrument_profile: str = "general"
    start_measure_number: int | None = None
    show_measure_numbers: bool = True
    measure_number_mode: str = "all"
    title: str | None = None


class CorrectionRequest(BaseModel):
    original_musicxml: str
    deleted_source_ids: list[str] = []
    source_map_file_id: str | None = None
    options: ConversionOptionsDTO = ConversionOptionsDTO()


class CorrectionResponse(BaseModel):
    working_musicxml: str
    jianpu_text: str
    text_anchors: list[dict] = []
    text_hash: str
    svg_file_ids: list[str] = []
