from __future__ import annotations

from pydantic import BaseModel


class PipelineResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str

