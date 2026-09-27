from __future__ import annotations

from ...models.syntax.schemas import (
    SyntaxDiagnostic,
    SyntaxValidateRequest,
    SyntaxValidateResponse,
)
from ...services.syntax.validator import SyntaxValidator
from ...services.settings.settings_service import SettingsService

MAX_DIAGNOSTICS = 1000
TRUNCATED_MARKER_ID = "syntax-warning-truncated"


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
        lyrics, lyric_warnings = self.validator.validate_lyrics(req.jianpu_text)
        known_ids = {item.id for item in diagnostics}
        diagnostics.extend(
            item for item in lyric_warnings if item.id not in known_ids
        )
        if len(diagnostics) > MAX_DIAGNOSTICS:
            diagnostics = [
                *diagnostics[: MAX_DIAGNOSTICS - 1],
                SyntaxDiagnostic(
                    id=TRUNCATED_MARKER_ID,
                    message=f"语法错误过多，仅显示前 {MAX_DIAGNOSTICS - 1} 条",
                    line=diagnostics[MAX_DIAGNOSTICS - 1].line,
                    column=diagnostics[MAX_DIAGNOSTICS - 1].column,
                    start=diagnostics[MAX_DIAGNOSTICS - 1].start,
                    end=diagnostics[MAX_DIAGNOSTICS - 1].end,
                    severity="warning",
                ),
            ]
        return SyntaxValidateResponse(diagnostics=diagnostics, lyrics=lyrics)
