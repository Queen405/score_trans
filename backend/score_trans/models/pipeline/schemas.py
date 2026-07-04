from __future__ import annotations

from pydantic import BaseModel

from ..common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    TargetKeyOrAuto,
)
from ..render.schemas import RenderedSvgPage
from ..provenance.schemas import SourceTextAttachment, TextAnchor


class PipelineByFileIdRequest(BaseModel):
    file_id: str
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile = "general"
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
    overlay_file_id: str | None = None
    source_map_file_id: str | None = None
    overlay_svg_file_id: str | None = None
    text_anchors: list[TextAnchor] = []
    text_attachments: list[SourceTextAttachment] = []
    text_hash: str = ""
