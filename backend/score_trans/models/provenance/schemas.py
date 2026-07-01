from __future__ import annotations

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class MusicXmlLocator(BaseModel):
    attribute: str = "id"
    contains: str


class SourceElement(BaseModel):
    source_id: str
    inter_id: int
    shape: str
    grade: float
    bounds: BoundingBox
    hit_path: str
    musicxml_locator: MusicXmlLocator


class SourceMapSheet(BaseModel):
    sheet_index: int
    width: int
    height: int
    overlay_file: str
    elements: list[SourceElement] = Field(default_factory=list)


class SourceMap(BaseModel):
    version: int = 1
    sheets: list[SourceMapSheet] = Field(default_factory=list)


class TextAnchor(BaseModel):
    source_id: str
    start_utf16: int
    end_utf16: int
    role: str
    valid: bool = True


class RenderAnchor(BaseModel):
    source_id: str
    page_index: int
    bbox: BoundingBox | None = None
    selector: str | None = None
