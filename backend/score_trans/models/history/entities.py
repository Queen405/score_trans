from __future__ import annotations

from dataclasses import dataclass, field

from ..provenance.schemas import SourceTextAttachment, TextAnchor
from ..render.layout import PUBLICATION_ENGINE_VERSION


@dataclass(slots=True)
class HistoryPage:
    id: int = 0
    batch_id: int = 0
    input_file_name: str = ""
    input_file_id: str = ""
    source_document_file_id: str = ""
    source_document_name: str = ""
    source_page_index: int = -1
    source_rotation: int = 0
    task_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    text_attachments: list[SourceTextAttachment] = field(default_factory=list)
    svg_file_id: str = ""
    engine_version: str = PUBLICATION_ENGINE_VERSION
    document_revision: str = ""
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = field(default_factory=list)
    text_anchor_baseline_text: str = ""
    text_anchor_baseline_anchors: list[TextAnchor] = field(default_factory=list)
    status: str = "completed"
    error_message: str = ""
    completed_at: str = ""
    position: int = 0
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""
    deleted_source_ids: list[str] = field(default_factory=list)
    recognition_candidate_selections: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class HistoryRenderPageOcrText:
    page_index: int = 0
    ocr_text: str = ""


@dataclass(slots=True)
class HistoryBatch:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    jianpu_text: str = ""
    render_page_file_ids: list[str] = field(default_factory=list)
    engine_version: str = PUBLICATION_ENGINE_VERSION
    render_layout_key: str = ""
    document_revision: str = ""
    render_page_ocr_texts: list[HistoryRenderPageOcrText] = field(default_factory=list)
    render_output_stale: bool = False
    pages: list[HistoryPage] = field(default_factory=list)


@dataclass(slots=True)
class HistoryBatchSummary:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    first_file_name: str = ""
    last_completed_at: str = ""


@dataclass(slots=True)
class JianpuSnapshot:
    id: int = 0
    batch_id: int = 0
    jianpu_text: str = ""
    source: str = "save"
    created_at: str = ""
