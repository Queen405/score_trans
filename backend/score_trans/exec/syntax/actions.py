from __future__ import annotations

from ...models.syntax.schemas import (
    SyntaxDiagnostic,
    SyntaxValidateRequest,
    SyntaxValidateResponse,
)
from ...services.syntax.validator import SyntaxValidator


class SyntaxActions:
    def __init__(self, validator: SyntaxValidator | None = None) -> None:
        self.validator = validator or SyntaxValidator()

    def validate(self, req: SyntaxValidateRequest) -> SyntaxValidateResponse:
        diagnostics = self.validator.validate(req.jianpu_text)
        if len(diagnostics) > 100:
            diagnostics = [
                *diagnostics[:99],
                SyntaxDiagnostic(
                    id="syntax-warning-truncated",
                    message="语法错误过多，仅显示前 99 条",
                    line=diagnostics[99].line,
                    column=diagnostics[99].column,
                    start=diagnostics[99].start,
                    end=diagnostics[99].end,
                    severity="warning",
                ),
            ]
        return SyntaxValidateResponse(diagnostics=diagnostics)
