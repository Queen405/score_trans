from __future__ import annotations

from pydantic import BaseModel, Field

from ..common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    TargetKeyOrAuto,
)
from ..provenance.schemas import RenderedTextBlock, SourceTextAttachment, TextAnchor
from .layout import PUBLICATION_ENGINE_VERSION, A4LayoutRequest


class RenderPageMeasureRange(BaseModel):
    source_page_index: int
    start_measure_number: int | None = None
    end_measure_number: int | None = None


class RenderPageOcrText(BaseModel):
    page_index: int
    ocr_text: str


class RenderedSvgPage(BaseModel):
    svg_file_id: str
    page_index: int
    page_width: float
    page_height: float
    measure_ranges: list[RenderPageMeasureRange] = []
    ocr_text: str | None = None
    render_map_file_id: str | None = None
    note_index_start: int | None = None
    note_index_end: int | None = None
    note_group_start: int | None = None
    note_group_end: int | None = None
    playback_start_tick: int | None = None
    playback_end_tick: int | None = None
    text_blocks: list[RenderedTextBlock] = []
    engine_version: str = PUBLICATION_ENGINE_VERSION
    layout_key: str = ""
    document_revision: str | None = None


class RenderJianpuSvgRequest(A4LayoutRequest):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)
    title: str | None = None


class RenderJianpuSvgResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage] = []


class RenderJianpuTextSvgRequest(A4LayoutRequest):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    page_image_file_id: str | None = None
    ocr_text: str | None = None
    include_ocr_text: bool = True
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)
    title: str = "简谱"
    text_anchors: list[TextAnchor] = []


class LiveJianpuSvgRequest(BaseModel):
    jianpu_text: str
    title: str = "\u7b80\u8c31"
    show_measure_numbers: bool | None = False
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)


class LiveJianpuSvgResponse(BaseModel):
    svg: str
    jianpu_text: str


class RenderJianpuTextSvgResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage] = []
    ocr_text: str | None = None
    jianpu_text: str | None = None


class NormalizeJianpuTextRequest(BaseModel):
    jianpu_text: str
    title: str = "简谱"


class NormalizeJianpuTextResponse(BaseModel):
    jianpu_text: str


class FinalRenderRequest(A4LayoutRequest):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)
    title: str | None = None


class FinalRenderResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage] = []
    page_width: float
    page_height: float


class PreservingLayoutRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)
    title: str | None = None


class PreservingLayoutResponse(BaseModel):
    svg_file_id: str
    page_width: float
    page_height: float


class BatchRenderPageRequest(BaseModel):
    musicxml_file_id: str | None = None
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    input_file_name: str | None = None
    page_image_file_id: str | None = None
    source_map_file_id: str | None = None
    ocr_text: str | None = None
    text_attachments: list[SourceTextAttachment] = []
    include_ocr_text: bool = False
    title: str | None = None
    source_page_index: int | None = Field(default=None, ge=0)
    text_anchors: list[TextAnchor] = []


class BatchRenderRequest(A4LayoutRequest):
    pages: list[BatchRenderPageRequest]
    source_pages: list[BatchRenderPageRequest] = []
    render_page_ocr_texts: list[RenderPageOcrText] = []
    target_key: TargetKeyOrAuto = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile | None = None
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    initial_measure_number: int = Field(default=1, ge=1)
    title: str = "简谱"


class BatchRenderResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage]
    page_width: float
    page_height: float
