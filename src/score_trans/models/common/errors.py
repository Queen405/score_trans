from __future__ import annotations


class ExternalToolError(RuntimeError):
    """Raised when an external CLI tool fails."""


class OCRError(RuntimeError):
    """Raised when OCR provider calls or response parsing fail."""

