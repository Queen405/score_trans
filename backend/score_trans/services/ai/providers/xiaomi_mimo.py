"""Xiaomi MiMo vision provider for AI transcription."""
from __future__ import annotations

from pathlib import Path

from ..core.config import (
    AI_API_KEY,
    AI_SYSTEM_MSG,
    AI_TEMPERATURE,
    AI_TIMEOUT,
)
from ..core.parsing import parse_vision_page_result
from ..core.prompts import (
    _load_prompt_config,
    build_jianpu_prompt,
    persisted_ai_settings,
)
from ..core.registry import register_provider
from ..core.schemas import VisionPageResult
from ._http import chat_completions
from ....utils.media import image_to_data_url
from ....models.common.errors import AITranscriptionError
from ....models.settings.provider_profiles import resolve_provider_profile_or_default

_BASE_URL = "https://api.xiaomimimo.com/v1"
_DEFAULT_MODEL = "mimo-v2.5"


class XiaomiMiMoProvider:
    """MiMo-V2.5 全模态模型，原生支持图片理解。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = AI_TIMEOUT,
        dry_run: bool = False,
    ) -> None:
        persisted = persisted_ai_settings()
        profile = resolve_provider_profile_or_default("ai", persisted.get("ai_provider"))
        profile_matches = profile.provider == "xiaomi_mimo"
        self.base_url = (
            base_url
            or (profile.base_url if profile_matches else "")
            or _BASE_URL
        ).rstrip("/")
        self.model = model or (profile.model if profile_matches else "") or _DEFAULT_MODEL
        self.api_key = api_key or persisted.get("ai_api_key") or AI_API_KEY
        self.timeout = timeout
        self.dry_run = dry_run

    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if not self.api_key and not self.dry_run:
            raise AITranscriptionError("AI API key not configured. Set it in Settings.")

        prompt = build_jianpu_prompt(
            target_key=target_key,
            title=title,
            page_index=page_index,
            extra_prompt=extra_prompt,
        )
        if self.dry_run:
            return VisionPageResult(
                title=title,
                key=target_key,
                meter="4/4",
                jianpu_text=f"title={title or 'AI 简谱'}\n1={target_key}\n4/4\n1 2 3 4 |",
                warnings=["dry_run: request was not sent"],
                confidence=1.0,
            )

        system_message = (
            _load_prompt_config().get("system_message")
            or AI_SYSTEM_MSG
            or "You are a careful sheet-music to numbered-notation transcription agent."
        )
        messages = [
            {"role": "system", "content": system_message},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_to_data_url(path)}},
                ],
            },
        ]
        try:
            content = chat_completions(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model,
                messages=messages,
                temperature=AI_TEMPERATURE,
                timeout=self.timeout,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise AITranscriptionError(f"AI transcription request failed: {exc}") from exc

        return parse_vision_page_result(content)


register_provider("xiaomi_mimo", XiaomiMiMoProvider)
register_provider("mimo", XiaomiMiMoProvider)
