from __future__ import annotations

from ...domain.parse.jianpu_text import validate_jianpu_text
from ...models.syntax.schemas import SyntaxDiagnostic


class SyntaxValidator:
    def validate(self, text: str) -> list[SyntaxDiagnostic]:
        return validate_jianpu_text(text)
