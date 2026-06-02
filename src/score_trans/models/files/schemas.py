from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int

