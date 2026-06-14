from __future__ import annotations

from pydantic import BaseModel

from ..common.types import AccidentalMode


class PipelineByFileIdRequest(BaseModel):
    file_id: str
    target_key: str = "C"
    accidental_mode: AccidentalMode = "auto"
    start_measure_number: int | None = None
    title: str | None = None


class PipelineResponse(BaseModel):
    musicxml_file_id: str
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str
    ocr_measure_numbers: list[int] = []
