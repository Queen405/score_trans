from __future__ import annotations

from pydantic import BaseModel


class RecognizeResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    musicxml_filename: str

