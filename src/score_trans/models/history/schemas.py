from __future__ import annotations

from pydantic import BaseModel


class PageCreate(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    svg_file_id: str = ""
    status: str = "completed"
    error_message: str = ""


class PageUpdate(BaseModel):
    musicxml_file_id: str | None = None
    jianpu_text: str | None = None
    ocr_text: str | None = None
    svg_file_id: str | None = None
    status: str | None = None
    error_message: str | None = None


class PageResponse(BaseModel):
    id: int
    input_file_name: str
    input_file_id: str
    musicxml_file_id: str
    jianpu_text: str
    ocr_text: str
    svg_file_id: str
    status: str
    error_message: str


class BatchCreateRequest(BaseModel):
    pages: list[PageCreate]


class BatchResponse(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    pages: list[PageResponse]


class BatchListItem(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    first_file_name: str


class DeleteAllResponse(BaseModel):
    deleted_count: int

