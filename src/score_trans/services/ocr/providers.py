from __future__ import annotations

from pathlib import Path
from typing import Any

from ...models.score import OCRTextBlock
from .client import build_request, send_request
from .parser import parse_openai_compatible_response
from .protocols import OCRProvider, OCRRequest
from .utils import (
    DEFAULT_OCR_BASE_URL,
    DEFAULT_OCR_FALLBACK_MODEL,
    DEFAULT_OCR_MODEL,
    _ocr_blocks_are_useful,
    is_deepseek_ocr_model,
)


class MockOCRProvider:
    def __init__(self, blocks: list[OCRTextBlock] | None = None) -> None:
        self.blocks = list(blocks or [])
        self.calls: list[Path] = []

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        self.calls.append(Path(image_path))
        return list(self.blocks)


class OpenAICompatibleOCRProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        dry_run: bool = False,
    ) -> None:
        from .utils import persisted_ocr_settings

        persisted = persisted_ocr_settings()
        self.base_url = (
            base_url
            or persisted.get("ocr_base_url")
            or DEFAULT_OCR_BASE_URL
        ).rstrip("/")
        self.model = model or persisted.get("ocr_model") or DEFAULT_OCR_MODEL
        self.fallback_model = persisted.get("ocr_fallback_model") or DEFAULT_OCR_FALLBACK_MODEL
        self.api_key = persisted.get("ocr_api_key")
        self.timeout = timeout
        self.dry_run = dry_run

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        blocks = self._recognize_with_model(image_path, self.model)
        if _ocr_blocks_are_useful(blocks) or not is_deepseek_ocr_model(self.model):
            return blocks
        return self._recognize_with_model(image_path, self.fallback_model)

    def build_request(self, image_path: str | Path, *, model: str | None = None) -> OCRRequest:
        return build_request(
            image_path,
            model=model or self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            dry_run=self.dry_run,
        )

    def _recognize_with_model(self, image_path: str | Path, model: str) -> list[OCRTextBlock]:
        request = self.build_request(image_path, model=model)
        if self.dry_run:
            return []

        response = send_request(request, self.timeout)
        return parse_openai_compatible_response(response)
