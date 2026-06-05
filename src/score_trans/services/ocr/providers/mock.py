from __future__ import annotations

from pathlib import Path

from score_trans.models.score import OCRTextBlock


class MockOCRProvider:
    def __init__(self, blocks: list[OCRTextBlock] | None = None) -> None:
        self.blocks = list(blocks or [])
        self.calls: list[Path] = []

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        self.calls.append(Path(image_path))
        return list(self.blocks)
