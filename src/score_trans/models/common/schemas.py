from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    stage: str | None = Field(
        None,
        description="出错阶段：audiveris / ocr / convert / render / export",
    )

