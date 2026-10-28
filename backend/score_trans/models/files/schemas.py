from __future__ import annotations

from typing import Literal

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


class RotateFileRequest(BaseModel):
    direction: Literal["left", "right"]


class FilesExistRequest(BaseModel):
    file_ids: list[str]


class FilesExistResponse(BaseModel):
    files: dict[str, bool]
