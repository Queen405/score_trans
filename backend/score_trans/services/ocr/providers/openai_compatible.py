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

from score_trans.models.common.errors import OCRError
from score_trans.models.score import OCRTextBlock
from score_trans.services.settings.api_keys import provider_api_key
from score_trans.services.settings.provider_profiles import (
    resolve_provider_profile_or_default,
)
from score_trans.utils.json_parsing import content_to_text
from score_trans.utils.media import image_to_data_url
from ..client.client import ocr_prompt_for_model
from ..core.utils import (
    _ocr_blocks_are_useful,
    is_deepseek_ocr_model,
)
from ..parsing import parse_openai_compatible_response
from ..parsing.parser import plain_text_to_blocks
from ._http import chat_completions


class OpenAICompatibleOCRProvider:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        fallback_model: str | None = None,
        timeout: float = OCR_TIMEOUT,
        dry_run: bool = False,
    ) -> None:
        from ..core import persisted_ocr_settings

        persisted = persisted_ocr_settings()
        profile = resolve_provider_profile_or_default(
            "ocr", persisted.get("ocr_provider")
        )
        profile_matches = profile.provider == "openai_compatible"
        self.base_url = (
            base_url
            or (profile.base_url if profile_matches else "")
            or DEFAULT_OCR_BASE_URL
        ).rstrip("/")
        self.model = (
            model or (profile.model if profile_matches else "") or DEFAULT_OCR_MODEL
        )
        self.fallback_model = (
            fallback_model
            or (profile.fallback_model if profile_matches else "")
            or persisted.get("ocr_fallback_model")
            or DEFAULT_OCR_FALLBACK_MODEL
        )
        self.api_key = api_key or provider_api_key(persisted, "ocr", profile.id) or ""
        self.timeout = timeout
        self.dry_run = dry_run

    def recognize(self, image_path: str | Path) -> list[OCRTextBlock]:
        blocks = self._recognize_with_model(image_path, self.model)
        if _ocr_blocks_are_useful(blocks) or not is_deepseek_ocr_model(self.model):
            return blocks
        return self._recognize_with_model(image_path, self.fallback_model)

    def _recognize_with_model(
        self, image_path: str | Path, model: str
    ) -> list[OCRTextBlock]:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        if not self.api_key and not self.dry_run:
            raise OCRError("OCR API key not configured. Set it in Settings.")

        if self.dry_run:
            return []

        prompt = ocr_prompt_for_model(model)
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(path)},
                    },
                ],
            }
        ]

        extra: dict[str, Any] = {}
        if not is_deepseek_ocr_model(model):
            extra["response_format"] = {"type": "json_object"}

        try:
            content = chat_completions(
                base_url=self.base_url,
                api_key=self.api_key,
                model=model,
                messages=messages,
                temperature=OCR_TEMPERATURE,
                max_tokens=OCR_MAX_TOKENS,
                timeout=self.timeout,
                **extra,
            )
        except Exception as exc:
            raise OCRError(f"OCR request failed: {exc}") from exc

        try:
            return parse_openai_compatible_response(
                {"choices": [{"message": {"content": content}}]}
            )
        except Exception:
            return plain_text_to_blocks(content_to_text(content))
