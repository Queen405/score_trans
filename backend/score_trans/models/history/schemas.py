from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..provenance.schemas import SourceTextAttachment, TextAnchor
from ..render.layout import PUBLICATION_ENGINE_VERSION


class PageCreate(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    task_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    text_attachments: list[SourceTextAttachment] = Field(default_factory=list)
    svg_file_id: str = ""
    engine_version: str = PUBLICATION_ENGINE_VERSION
    document_revision: str = ""
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = Field(default_factory=list)
    status: str = "completed"
    error_message: str = ""
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
    deleted_source_ids: list[str] = Field(default_factory=list)


class PageUpdate(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str | None = None
    jianpu_text: str | None = None
    ocr_text: str | None = None
    text_attachments: list[SourceTextAttachment] | None = None
    svg_file_id: str | None = None
    engine_version: str | None = None
    document_revision: str | None = None
    overlay_svg_file_id: str | None = None
    overlay_file_id: str | None = None
    source_map_file_id: str | None = None
    text_hash: str | None = None
    text_anchors: list[TextAnchor] | None = None
    status: str | None = None
    error_message: str | None = None
    omr_file_id: str | None = None
    original_musicxml: str | None = None
    working_musicxml: str | None = None
    deleted_source_ids: list[str] | None = None


class PageResponse(BaseModel):
    id: int
    batch_id: int
    input_file_name: str
    input_file_id: str
    task_id: str
    musicxml_file_id: str
    jianpu_text: str
    ocr_text: str
    text_attachments: list[SourceTextAttachment] = Field(default_factory=list)
    svg_file_id: str
    engine_version: str = PUBLICATION_ENGINE_VERSION
    document_revision: str = ""
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = Field(default_factory=list)
    status: str
    error_message: str
    completed_at: str = ""
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
    deleted_source_ids: list[str] = Field(default_factory=list)


class RenderPageOcrText(BaseModel):
    page_index: int
    ocr_text: str


class BatchCreateRequest(BaseModel):
    pages: list[PageCreate]
    jianpu_text: str = ""
    render_page_file_ids: list[str] = Field(default_factory=list)
    render_page_ocr_texts: list[RenderPageOcrText] = Field(default_factory=list)
    render_output_stale: bool = False
    render_layout_key: str = ""


class BatchResponse(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    jianpu_text: str = ""
    render_page_file_ids: list[str] = Field(default_factory=list)
    engine_version: str = PUBLICATION_ENGINE_VERSION
    render_layout_key: str = ""
    document_revision: str = ""
    render_page_ocr_texts: list[RenderPageOcrText] = Field(default_factory=list)
    render_output_stale: bool = False
    pages: list[PageResponse]


class BatchListItem(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    first_file_name: str
    last_completed_at: str = ""


class DeleteAllResponse(BaseModel):
    deleted_count: int


class BatchRenderPagesUpdate(BaseModel):
    render_page_file_ids: list[str]
    render_output_stale: bool = False
    render_layout_key: str = ""


class BatchJianpuTextUpdate(BaseModel):
    jianpu_text: str
    source: Literal["save", "reset", "auto"] = "save"


class JianpuSnapshotItem(BaseModel):
    id: int
    batch_id: int
    jianpu_text: str
    source: str
    created_at: str


class BatchRenderPageOcrTextsUpdate(BaseModel):
    pages: list[RenderPageOcrText]
    render_output_stale: bool = True


class BatchPageOrderItem(BaseModel):
    page_id: int
    jianpu_text: str = ""


class BatchPageOrderRequest(BaseModel):
    jianpu_text: str
    pages: list[BatchPageOrderItem]
