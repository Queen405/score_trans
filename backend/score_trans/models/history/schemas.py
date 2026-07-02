from __future__ import annotations

from pydantic import BaseModel

from ..provenance.schemas import SourceTextAttachment, TextAnchor


class PageCreate(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    task_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    text_attachments: list[SourceTextAttachment] = []
    svg_file_id: str = ""
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = []
    start_measure_number: int | None = None
    status: str = "completed"
    error_message: str = ""


class PageUpdate(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str | None = None
    jianpu_text: str | None = None
    ocr_text: str | None = None
    text_attachments: list[SourceTextAttachment] | None = None
    svg_file_id: str | None = None
    overlay_svg_file_id: str | None = None
    overlay_file_id: str | None = None
    source_map_file_id: str | None = None
    text_hash: str | None = None
    text_anchors: list[TextAnchor] | None = None
    start_measure_number: int | None = None
    status: str | None = None
    error_message: str | None = None


class PageResponse(BaseModel):
    id: int
    batch_id: int
    input_file_name: str
    input_file_id: str
    task_id: str
    musicxml_file_id: str
    jianpu_text: str
    ocr_text: str
    text_attachments: list[SourceTextAttachment] = []
    svg_file_id: str
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = []
    start_measure_number: int | None = None
    status: str
    error_message: str
    completed_at: str = ""


class RenderPageOcrText(BaseModel):
    page_index: int
    ocr_text: str


class BatchCreateRequest(BaseModel):
    pages: list[PageCreate]
    jianpu_text: str = ""
    render_page_file_ids: list[str] = []
    render_page_ocr_texts: list[RenderPageOcrText] = []


class BatchResponse(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    jianpu_text: str = ""
    render_page_file_ids: list[str] = []
    render_page_ocr_texts: list[RenderPageOcrText] = []
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


class BatchJianpuTextUpdate(BaseModel):
    jianpu_text: str


class BatchRenderPageOcrTextsUpdate(BaseModel):
    pages: list[RenderPageOcrText]


class BatchPageOrderItem(BaseModel):
    page_id: int
    jianpu_text: str = ""
    start_measure_number: int | None = None


class BatchPageOrderRequest(BaseModel):
    jianpu_text: str
    pages: list[BatchPageOrderItem]
