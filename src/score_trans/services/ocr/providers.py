from __future__ import annotations

from pathlib import Path
from typing import Any

from score_trans.config.settings import (
    OCR_BASE_URL as DEFAULT_OCR_BASE_URL,
)
from score_trans.config.settings import (
    OCR_FALLBACK_MODEL as DEFAULT_OCR_FALLBACK_MODEL,
)
from score_trans.config.settings import (
    OCR_MAX_TOKENS,
    OCR_MODEL as DEFAULT_OCR_MODEL,
    OCR_TEMPERATURE,
    OCR_TIMEOUT,
)

from ...models.common.errors import OCRError
from ...models.score import OCRTextBlock
from ...utils.media import image_to_data_url
from .client import ocr_prompt_for_model
from .parser import parse_openai_compatible_response, plain_text_to_blocks
from .protocols import OCRProvider
from .utils import (
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
        timeout: float = OCR_TIMEOUT,
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
        self.api_key = persisted.get("ocr_api_key") or ""
        self.timeout = timeout
        self.dry_run = dry_run
        self._chat: Any = None

    def _get_chat(self, model: str | None = None) -> Any:
        """延迟初始化并复用 ChatOpenAI 实例。"""
        if self._chat is None:
            from langchain_openai import ChatOpenAI
            resolved = model or self.model
            kwargs: dict[str, Any] = {}
            if not is_deepseek_ocr_model(resolved):
                kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
            self._chat = ChatOpenAI(
                model=resolved,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=OCR_TEMPERATURE,
                timeout=self.timeout,
                max_tokens=OCR_MAX_TOKENS,
                **kwargs,
            )
        return self._chat

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        blocks = self._recognize_with_model(image_path, self.model)
        if _ocr_blocks_are_useful(blocks) or not is_deepseek_ocr_model(self.model):
            return blocks
        self._chat = None
        return self._recognize_with_model(image_path, self.fallback_model)

    def _recognize_with_model(self, image_path: str | Path, model: str) -> list[OCRTextBlock]:
        from langchain_core.messages import HumanMessage
        from ...utils.json_parsing import content_to_text

        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        if not self.api_key and not self.dry_run:
            raise OCRError("OCR API key not configured. Set it in Settings.")

        if self.dry_run:
            return []

        chat = self._get_chat(model)
        prompt = ocr_prompt_for_model(model)

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_to_data_url(path)}},
            ]
        )

        try:
            response = chat.invoke([message])
        except Exception as exc:
            raise OCRError(f"OCR request failed: {exc}") from exc

        content = getattr(response, "content", str(response))

        try:
            return parse_openai_compatible_response(
                {"choices": [{"message": {"content": content}}]}
            )
        except Exception:
            return plain_text_to_blocks(content_to_text(content))
