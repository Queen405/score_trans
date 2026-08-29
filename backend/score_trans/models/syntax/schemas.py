from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SyntaxSeverity = Literal["error", "warning"]


class SyntaxDiagnostic(BaseModel):
    id: str
    message: str
    line: int = Field(description="1-based source line for display")
    column: int = Field(description="1-based code-point column for display only")
    start: int = Field(description="UTF-16 code-unit start offset for editor selection")
    end: int = Field(description="UTF-16 code-unit end offset for editor selection")
    severity: SyntaxSeverity = "error"
    measure: str | None = Field(
        default=None,
        description="关联小节的显示编号（仅小节级诊断提供）",
    )


class SyntaxValidateRequest(BaseModel):
    jianpu_text: str


class SyntaxValidateResponse(BaseModel):
    diagnostics: list[SyntaxDiagnostic]
