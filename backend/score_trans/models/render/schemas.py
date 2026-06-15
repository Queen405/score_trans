from __future__ import annotations

from pydantic import BaseModel

from ..common.types import AccidentalMode, MeasureNumberMode, TargetKey


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


class RenderJianpuSvgRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    start_measure_number: int | None = None
    title: str | None = None


class RenderJianpuSvgResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage] = []


class RenderJianpuTextSvgRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    page_image_file_id: str | None = None
    ocr_text: str | None = None
    include_ocr_text: bool = True
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    title: str = "简谱"
    start_measure_number: int | None = None


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


class FinalRenderRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    start_measure_number: int | None = None
    title: str | None = None


class FinalRenderResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage] = []
    page_width: float
    page_height: float


class PreservingLayoutRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    start_measure_number: int | None = None
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
    ocr_text: str | None = None
    include_ocr_text: bool = False
    start_measure_number: int | None = None
    title: str | None = None


class BatchRenderRequest(BaseModel):
    pages: list[BatchRenderPageRequest]
    source_pages: list[BatchRenderPageRequest] = []
    render_page_ocr_texts: list[RenderPageOcrText] = []
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    show_measure_numbers: bool | None = None
    measure_number_mode: MeasureNumberMode = "all"
    title: str = "简谱"


class BatchRenderResponse(BaseModel):
    svg_file_id: str
    pages: list[RenderedSvgPage]
    page_width: float
    page_height: float
