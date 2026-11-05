from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..provenance.schemas import SourceTextAttachment, TextAnchor
from ..render.layout import PUBLICATION_ENGINE_VERSION


class PageCreate(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    source_document_file_id: str = ""
    source_document_name: str = ""
    source_page_index: int = -1
    source_rotation: Literal[0, 90, 180, 270] = 0
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
    text_anchor_baseline_text: str | None = None
    text_anchor_baseline_anchors: list[TextAnchor] | None = None
    status: str = "completed"
    error_message: str = ""
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
    deleted_source_ids: list[str] = Field(default_factory=list)
    recognition_candidate_selections: dict[str, str] = Field(default_factory=dict)


class PageUpdate(BaseModel):
    input_file_name: str | None = None
    input_file_id: str | None = None
    source_rotation: Literal[0, 90, 180, 270] | None = None
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
    text_anchor_baseline_text: str | None = None
    text_anchor_baseline_anchors: list[TextAnchor] | None = None
    status: str | None = None
    error_message: str | None = None
    omr_file_id: str | None = None
    original_musicxml: str | None = None
    working_musicxml: str | None = None
    deleted_source_ids: list[str] | None = None
    recognition_candidate_selections: dict[str, str] | None = None


class PageResponse(BaseModel):
    id: int
    batch_id: int
    input_file_name: str
    input_file_id: str
    source_document_file_id: str = ""
    source_document_name: str = ""
    source_page_index: int = -1
    source_rotation: Literal[0, 90, 180, 270] = 0
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
    text_anchor_baseline_text: str = ""
    text_anchor_baseline_anchors: list[TextAnchor] = Field(default_factory=list)
    status: str
    error_message: str
    completed_at: str = ""
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
    deleted_source_ids: list[str] = Field(default_factory=list)
    recognition_candidate_selections: dict[str, str] = Field(default_factory=dict)


class RenderPageOcrText(BaseModel):
    page_index: int
    ocr_text: str


class BatchSavePage(BaseModel):
    page_id: int
    task_id: str
    musicxml_file_id: str
    jianpu_text: str
    ocr_text: str
    text_attachments: list[SourceTextAttachment]
    svg_file_id: str
    overlay_file_id: str
    source_map_file_id: str
    text_hash: str
    text_anchors: list[TextAnchor]
    text_anchor_baseline_text: str | None = None
    text_anchor_baseline_anchors: list[TextAnchor] | None = None
    status: str
    error_message: str
    omr_file_id: str
    original_musicxml: str
    working_musicxml: str
    deleted_source_ids: list[str]
    recognition_candidate_selections: dict[str, str] = Field(default_factory=dict)


class BatchRenderStateUpdate(BaseModel):
    render_page_file_ids: list[str]
    render_page_ocr_texts: list[RenderPageOcrText]
    render_output_stale: bool
    render_layout_key: str

    @model_validator(mode="after")
    def validate_render_state(self) -> BatchRenderStateUpdate:
        if not self.render_output_stale and not self.render_page_file_ids:
            raise ValueError(
                "render_page_file_ids must not be empty when render output is fresh"
            )
        indexes = [item.page_index for item in self.render_page_ocr_texts]
        if any(index < 0 for index in indexes) or len(indexes) != len(set(indexes)):
            raise ValueError(
                "render_page_ocr_texts page_index values must be unique and non-negative"
            )
        return self


class BatchSaveRequest(BatchRenderStateUpdate):
    jianpu_text: str
    source: Literal["save", "reset"] = "save"
    pages: list[BatchSavePage]


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


class BatchRenderStateResponse(BaseModel):
    id: int
    render_page_file_ids: list[str] = Field(default_factory=list)
    engine_version: str = PUBLICATION_ENGINE_VERSION
    render_layout_key: str = ""
    render_page_ocr_texts: list[RenderPageOcrText] = Field(default_factory=list)
    render_output_stale: bool = False


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
