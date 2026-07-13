from __future__ import annotations

from dataclasses import dataclass, field

from ..provenance.schemas import SourceTextAttachment, TextAnchor


@dataclass(slots=True)
class HistoryPage:
    id: int = 0
    batch_id: int = 0
    input_file_name: str = ""
    input_file_id: str = ""
    task_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    text_attachments: list[SourceTextAttachment] = field(default_factory=list)
    svg_file_id: str = ""
    engine_version: str = "publication-2"
    document_revision: str = ""
    overlay_svg_file_id: str = ""
    overlay_file_id: str = ""
    source_map_file_id: str = ""
    text_hash: str = ""
    text_anchors: list[TextAnchor] = field(default_factory=list)
    start_measure_number: int | None = None
    status: str = "completed"
    error_message: str = ""
    completed_at: str = ""
    position: int = 0
    omr_file_id: str = ""
    original_musicxml: str = ""
    working_musicxml: str = ""


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
    engine_version: str = "publication-2"
    document_revision: str = ""
    render_page_ocr_texts: list[HistoryRenderPageOcrText] = field(default_factory=list)
    pages: list[HistoryPage] = field(default_factory=list)


@dataclass(slots=True)
class HistoryBatchSummary:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    first_file_name: str = ""
    last_completed_at: str = ""
