from __future__ import annotations


class ExternalToolError(RuntimeError):
    """Raised when an external CLI tool fails.

    Carries optional ``stdout``/``stderr`` attributes with the raw captured
    output so callers can inspect details without it being dumped into the
    user-facing message via ``str()``.
    """

    def __init__(
        self,
        message: str,
        *,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


class OCRError(RuntimeError):
    """Raised when OCR provider calls or response parsing fail."""


class AITranscriptionError(RuntimeError):
    """Raised when AI score transcription calls or response parsing fail."""


class RenderError(RuntimeError):
    """Raised when score rendering cannot produce a usable output."""


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file or request exceeds its configured limit."""


class CodedValidationError(ValueError):
    """A validation error carrying a stable machine-readable code.

    The API layer registers a dedicated handler for this class so subclasses
    are dispatched ahead of plain ``ValueError`` (Starlette walks the MRO) and
    produce ``{"error", "stage": "validation", "code"}`` responses.
    """

    error_code: str = ""
