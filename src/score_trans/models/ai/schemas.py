from __future__ import annotations

from pydantic import BaseModel, Field


class AiTranscribeRequest(BaseModel):
    file_id: str
    target_key: str = "C"
    title: str | None = None
    render_dpi: int = Field(default=220, ge=72, le=400)
    max_pages: int | None = Field(default=None, ge=1, le=100)
    prompt: str | None = None
    normalize: bool = True


class AiTranscribedPage(BaseModel):
    page_index: int
    page_image_file_id: str
    page_image_filename: str
    title: str | None = None
    key: str | None = None
    meter: str | None = None
    tempo: str | None = None
    jianpu_text: str
    warnings: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    confidence: float | None = None


class AiTranscribeResponse(BaseModel):
    source_file_id: str
    source_filename: str
    target_key: str
    title: str | None = None
    merged_jianpu_text: str
    jianpu_file_id: str
    pages: list[AiTranscribedPage]
    warnings: list[str] = Field(default_factory=list)
