from __future__ import annotations

from pydantic import BaseModel


class RenderJianpuSvgRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str | None = None
    target_key: str = "C"
    start_measure_number: int | None = None
    title: str | None = None


class RenderJianpuSvgResponse(BaseModel):
    svg_file_id: str


class RenderJianpuTextSvgRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    page_image_file_id: str | None = None
    ocr_text: str | None = None
    include_ocr_text: bool = True
    title: str = "简谱"
    start_measure_number: int | None = None


class RenderJianpuTextSvgResponse(BaseModel):
    svg_file_id: str
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
    target_key: str = "C"
    start_measure_number: int | None = None
    title: str | None = None


class FinalRenderResponse(BaseModel):
    svg_file_id: str
    page_width: float
    page_height: float


class PreservingLayoutRequest(BaseModel):
    musicxml_file_id: str
    page_image_file_id: str
    target_key: str = "C"
    start_measure_number: int | None = None
    title: str | None = None


class PreservingLayoutResponse(BaseModel):
    svg_file_id: str
    page_width: float
    page_height: float

