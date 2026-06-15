from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HistoryPage:
    id: int = 0
    batch_id: int = 0
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    svg_file_id: str = ""
    start_measure_number: int | None = None
    status: str = "completed"
    error_message: str = ""


@dataclass(slots=True)
class HistoryBatch:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    render_page_file_ids: list[str] = field(default_factory=list)
    pages: list[HistoryPage] = field(default_factory=list)


@dataclass(slots=True)
class HistoryBatchSummary:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    first_file_name: str = ""
