from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from score_trans.models.score import OCRTextBlock


class OCRProvider(Protocol):
    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        """Return OCR text blocks for an image file."""


@dataclass(slots=True)
class OCRRequest:
    endpoint: str
    headers: dict[str, str]
    payload: dict[str, Any]
