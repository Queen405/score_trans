from __future__ import annotations

from ...domain.parse.jianpu_text import validate_jianpu_text
from ...models.syntax.schemas import SyntaxDiagnostic


class SyntaxValidator:
    def validate(
        self,
        text: str,
        *,
        check_measure_durations: bool = False,
    ) -> list[SyntaxDiagnostic]:
        return validate_jianpu_text(
            text,
            check_measure_durations=check_measure_durations,
        )
