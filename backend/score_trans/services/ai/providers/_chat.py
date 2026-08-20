"""OpenAI-compatible chat provider base class for the workbench assistant."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ....config.settings import (
    AI_TEMPERATURE,
    AI_TIMEOUT,
    ASSISTANT_API_KEY,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
)
from ....models.common.errors import AITranscriptionError
from ..core.prompts import persisted_ai_settings
from ..core.registry import register_chat_provider
from ...settings.api_keys import provider_api_key
from ...settings.provider_profiles import resolve_provider_profile_or_default
from ._http import chat_completion_chunks, chat_completions

MAX_ASSISTANT_TOKENS = 4096


class OpenAICompatibleChatProvider:
    """Base class for chat providers that call OpenAI-compatible endpoints.

    Subclasses override ``thinking_kwargs()`` to translate the
    ``enable_thinking`` toggle into provider-specific request parameters.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout: float = AI_TIMEOUT,
    ) -> None:
        persisted = persisted_ai_settings()
        profile = resolve_provider_profile_or_default(
            "assistant", persisted.get("assistant_provider")
        )
        self.base_url = (
            base_url
            or persisted.get("assistant_base_url")
            or profile.base_url
            or ASSISTANT_BASE_URL
        ).rstrip("/")
        self.model = (
            model
            or persisted.get("assistant_model")
            or profile.model
            or ASSISTANT_MODEL
        )
        self.api_key = (
            api_key
            or provider_api_key(persisted, "assistant", profile.id)
            or ASSISTANT_API_KEY
        )
        self.timeout = timeout

    def thinking_kwargs(self, enable_thinking: bool | None) -> dict[str, Any]:
        """Return provider-specific body fields for the thinking toggle.

        Default uses top-level ``enable_thinking`` (DashScope / 百炼 format).
        When ``enable_thinking`` is None (unset), no params are sent so the
        provider's default applies.
        """
        if enable_thinking is None:
            return {}
        return {"enable_thinking": enable_thinking}

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool | None = None,
    ) -> str:
        if not self.api_key:
            raise AITranscriptionError(
                "工作台 AI API key 未配置，请在设置中填写 API Key。"
            )
        extra = self.thinking_kwargs(enable_thinking)
        return chat_completions(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            temperature=AI_TEMPERATURE,
            timeout=self.timeout,
            max_tokens=MAX_ASSISTANT_TOKENS,
            extra_body=extra or None,
        )

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool | None = None,
    ) -> Iterator[str]:
        if not self.api_key:
            raise AITranscriptionError(
                "工作台 AI API key 未配置，请在设置中填写 API Key。"
            )
        extra = self.thinking_kwargs(enable_thinking)
        yield from chat_completion_chunks(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            messages=messages,
            temperature=AI_TEMPERATURE,
            timeout=self.timeout,
            max_tokens=MAX_ASSISTANT_TOKENS,
            extra_body=extra or None,
        )


register_chat_provider("openai_compatible", OpenAICompatibleChatProvider)
register_chat_provider("dashscope", OpenAICompatibleChatProvider)
