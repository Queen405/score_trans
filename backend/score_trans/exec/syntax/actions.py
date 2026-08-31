from __future__ import annotations

from ...models.syntax.schemas import (
    SyntaxDiagnostic,
    SyntaxValidateRequest,
    SyntaxValidateResponse,
)
from ...services.syntax.validator import SyntaxValidator
from ...services.settings.settings_service import SettingsService


class SyntaxActions:
    def __init__(
        self,
        validator: SyntaxValidator | None = None,
        settings: SettingsService | None = None,
    ) -> None:
        self.validator = validator or SyntaxValidator()
        self.settings = settings or SettingsService()

    def validate(self, req: SyntaxValidateRequest) -> SyntaxValidateResponse:
        diagnostics = self.validator.validate(
            req.jianpu_text,
            check_measure_durations=self.settings.get_bool(
                "jianpu_measure_duration_check", True
            ),
        )
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
