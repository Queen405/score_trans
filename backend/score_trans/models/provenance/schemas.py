from __future__ import annotations

from typing import Literal

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


class TextPlacementAnchor(BaseModel):
    kind: Literal[
        "source_element",
        "score_start",
        "score_end",
        "source_relative",
    ]
    source_id: str | None = None
    relative_y: float | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    mapping_confidence: float | None = None


class SourceTextAttachment(BaseModel):
    id: str
    text: str
    role: str = "other"
    source_bbox: BoundingBox | None = None
    font_size: float | None = None
    ocr_confidence: float | None = None
    anchor: TextPlacementAnchor


class RenderedTextBlock(BaseModel):
    id: str
    source_page_index: int
    source_attachment_id: str
    text: str
    role: str = "other"
    bbox: BoundingBox
    font_size: float | None = None
    anchor: TextPlacementAnchor

