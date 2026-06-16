from __future__ import annotations

from pydantic import BaseModel

from ..common.types import AccidentalMode, MeasureNumberMode, TargetKey
from ..render.schemas import RenderedSvgPage


class PipelineByFileIdRequest(BaseModel):
    file_id: str
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    start_measure_number: int | None = None
    title: str | None = None


class PipelineResponse(BaseModel):
    musicxml_file_id: str
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str
    render_pages: list[RenderedSvgPage] = []
    ocr_measure_numbers: list[int] = []
    ocr_text: str = ""
