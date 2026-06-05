from __future__ import annotations

from pydantic import BaseModel


class UploadPage(BaseModel):
    file_id: str
    filename: str
    page_index: int


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    pages: list[UploadPage] | None = None

