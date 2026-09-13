from __future__ import annotations

from pydantic import BaseModel

from ..common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    PolyphonyMode,
    TargetKeyOrAuto,
)
from ..provenance.schemas import SourceTextAttachment, TextAnchor
from ..render.layout import A4LayoutRequest
from ..render.schemas import RenderedSvgPage


class PipelineByFileIdRequest(A4LayoutRequest):
    file_id: str
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile = "general"
    polyphony_mode: PolyphonyMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    title: str | None = None


class PipelineResponse(BaseModel):
    musicxml_file_id: str
    musicxml_text: str = ""
    omr_file_id: str | None = None
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str
    render_pages: list[RenderedSvgPage] = []
    ocr_text: str = ""
    overlay_file_id: str | None = None
    source_map_file_id: str | None = None
    overlay_svg_file_id: str | None = None
    text_anchors: list[TextAnchor] = []
    text_attachments: list[SourceTextAttachment] = []
    text_hash: str = ""
    warnings: list[str] = []
