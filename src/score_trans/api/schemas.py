from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── 通用 ──────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    stage: str | None = Field(
        None,
        description="出错阶段：audiveris / musescore / ocr / convert / render",
    )


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int


# ── 转换 ──────────────────────────────────────────────────────────────────────

class MusicXmlToJianpuRequest(BaseModel):
    musicxml_file_id: str
    target_key: str = "C"
    start_measure_number: int | None = None


class MusicXmlToJianpuResponse(BaseModel):
    jianpu_text: str
    jianpu_file_id: str | None = None


class JianpuToMusicXmlRequest(BaseModel):
    jianpu_text: str | None = None
    jianpu_file_id: str | None = None
    title: str = "Jianpu Import"


class JianpuToMusicXmlResponse(BaseModel):
    musicxml_text: str
    musicxml_file_id: str


# ── 渲染 ──────────────────────────────────────────────────────────────────────

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
    title: str = "简谱"


class RenderJianpuTextSvgResponse(BaseModel):
    svg_file_id: str


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


# ── 识别 ──────────────────────────────────────────────────────────────────────

class RecognizeResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    musicxml_filename: str


# ── 流水线 ────────────────────────────────────────────────────────────────────

class PipelineResponse(BaseModel):
    task_id: str | None = None
    musicxml_file_id: str
    jianpu_text: str
    jianpu_file_id: str
    svg_file_id: str


# ── 导出 ──────────────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    musicxml_file_id: str
    output_format: str = Field("pdf", pattern=r"^(pdf|png|mid|midi)$")
    filename: str | None = None


class ExportResponse(BaseModel):
    file_id: str
    filename: str


# ── 配置 ──────────────────────────────────────────────────────────────────────

class SettingsResponse(BaseModel):
    audiveris_path: str
    musescore_path: str
    java_home: str
    work_dir: str
    target_key: str = "C"
    output_dir: str = ""
    ocr_api_key: str = ""
    ocr_api_key_set: bool = False
    ocr_base_url: str = "https://api.siliconflow.cn/v1"
    ocr_model: str = "deepseek-ai/DeepSeek-OCR"
    omr_preprocess: bool = True
    omr_preprocess_long_edge: int = 3600
    omr_preprocess_binarize: bool = False


class SettingsUpdateRequest(BaseModel):
    audiveris_path: str | None = None
    musescore_path: str | None = None
    java_home: str | None = None
    output_dir: str | None = None
    ocr_api_key: str | None = None
    ocr_base_url: str | None = None
    ocr_model: str | None = None
    omr_preprocess: bool | None = None
    omr_preprocess_long_edge: int | None = None
    omr_preprocess_binarize: bool | None = None


# ── SSE 进度 ──────────────────────────────────────────────────────────────────

class SSEProgressEvent(BaseModel):
    task_id: str
    status: str
    stage: str
    percent: int
    message: str = ""
    error: str | None = None
    result: dict[str, Any] | None = None


# ── OCR 文字层渲染 ────────────────────────────────────────────────────────────

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
