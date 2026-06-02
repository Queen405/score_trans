from __future__ import annotations

from pydantic import BaseModel


class ExportResponse(BaseModel):
    file_id: str
    filename: str


class ExportMidiTextRequest(BaseModel):
    jianpu_text: str
    filename: str = "score.mid"
    title: str = "简谱"

