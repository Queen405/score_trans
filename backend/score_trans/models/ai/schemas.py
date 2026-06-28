from __future__ import annotations

from pydantic import BaseModel, Field

from score_trans.config.settings import PDF_RENDER_DPI
from score_trans.models.common.types import (
    AccidentalMode,
    InstrumentProfile,
    TargetKey,
)


class AiTranscribeRequest(BaseModel):
    file_id: str
    target_key: TargetKey = "C"
    accidental_mode: AccidentalMode = "auto"
    instrument_profile: InstrumentProfile = "general"
    title: str | None = None
    render_dpi: int = Field(default=PDF_RENDER_DPI, ge=72, le=400)
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
    tempo: str | int | None = None
    jianpu_text: str
    measure_number_candidates: list[int] = Field(default_factory=list)
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


class AiChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


class AiChatSessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class AiChatSessionCreateRequest(BaseModel):
    title: str | None = None


class AiChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    jianpu_text: str | None = None
    enable_thinking: bool | None = None


class AiChatResponse(BaseModel):
    session_id: str
    message: AiChatMessageResponse
    messages: list[AiChatMessageResponse]
