"""OpenAI-compatible chat provider base class for the workbench assistant."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from ....config.settings import (
    AI_TEMPERATURE,
    AI_TIMEOUT,
    ASSISTANT_API_KEY,
    ASSISTANT_BASE_URL,
    ASSISTANT_MAX_TOKENS,
    ASSISTANT_MODEL,
)
from ....models.common.errors import AITranscriptionError
from ...settings.api_keys import provider_api_key
from ...settings.provider_profiles import resolve_provider_profile_or_default
from ..core.prompts import persisted_ai_settings
from ..core.registry import register_chat_provider
from ._http import chat_completion_chunks, chat_completions

MAX_CONTINUATION_ROUNDS = 3
MIN_REPEAT_OVERLAP = 32
MAX_OVERLAP_CHECK = 240

_CONTINUATION_INSTRUCTION = (
    "你的上一条回复因输出长度限制被截断。"
    "请从上次停止的位置继续输出，不要重复已经输出过的内容。"
)
_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>\s*", re.DOTALL)


class OpenAICompatibleChatProvider:
    """Base class for chat providers that call OpenAI-compatible endpoints.

    Subclasses override ``thinking_kwargs()`` to translate the
    ``enable_thinking`` toggle into provider-specific request parameters.

    When a response is truncated (``finish_reason == "length"``), the provider
    automatically continues it for at most ``MAX_CONTINUATION_ROUNDS`` rounds.
    A missing finish_reason is treated as a normal completion for provider
    compatibility.
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
        # profile 的 max_tokens 优先，其次环境变量，最后 4096 兼容默认值。
        self.max_tokens = profile.max_tokens or ASSISTANT_MAX_TOKENS

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
        parts: list[str] = []
        for round_index in range(MAX_CONTINUATION_ROUNDS + 1):
            result = chat_completions(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model,
                messages=continuation_messages(messages, parts),
                temperature=AI_TEMPERATURE,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
                extra_body=extra or None,
            )
            _reject_stalled_round(round_index, result.content, "".join(parts))
            parts.append(result.content)
            if result.finish_reason != "length":
                return "".join(parts)
        raise _truncation_error(self.max_tokens)

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
        parts: list[str] = []
        for round_index in range(MAX_CONTINUATION_ROUNDS + 1):
            round_text: list[str] = []
            finish_reason: str | None = None
            for chunk in chat_completion_chunks(
                base_url=self.base_url,
                api_key=self.api_key,
                model=self.model,
                messages=continuation_messages(messages, parts),
                temperature=AI_TEMPERATURE,
                timeout=self.timeout,
                max_tokens=self.max_tokens,
                extra_body=extra or None,
            ):
                if chunk.text:
                    round_text.append(chunk.text)
                    yield chunk.text
                if chunk.finish_reason is not None:
                    finish_reason = chunk.finish_reason
            round_content = "".join(round_text)
            _reject_stalled_round(round_index, round_content, "".join(parts))
            if round_content:
                parts.append(round_content)
            if finish_reason != "length":
                return
        raise _truncation_error(self.max_tokens)


def continuation_messages(
    messages: list[dict[str, Any]],
    parts: list[str],
) -> list[dict[str, Any]]:
    """Return the request messages for the next continuation round.

    The first round uses the original messages. Continuation rounds append the
    accumulated assistant output (thinking blocks stripped when possible) plus
    an explicit "continue without repeating" instruction.
    """
    if not parts:
        return messages
    accumulated = "".join(parts)
    assistant_context = _THINK_BLOCK_RE.sub("", accumulated).strip() or accumulated
    return [
        *messages,
        {"role": "assistant", "content": assistant_context},
        {"role": "user", "content": _CONTINUATION_INSTRUCTION},
    ]


def _reject_stalled_round(round_index: int, round_content: str, previous: str) -> None:
    """Raise when a continuation round adds no new content or repeats output."""
    if round_index == 0:
        return
    if not round_content.strip():
        raise AITranscriptionError("工作台 AI 续写未产生新内容，已中止。")
    if round_content in previous:
        raise AITranscriptionError("工作台 AI 续写输出了重复内容，已中止。")
    if _repeat_overlap(previous, round_content) >= MIN_REPEAT_OVERLAP:
        raise AITranscriptionError("工作台 AI 续写输出了重复内容，已中止。")


def _repeat_overlap(previous: str, new_text: str) -> int:
    """Length of the longest suffix of ``previous`` matching a prefix of ``new_text``."""
    max_check = min(len(previous), len(new_text), MAX_OVERLAP_CHECK)
    for size in range(max_check, MIN_REPEAT_OVERLAP - 1, -1):
        if previous.endswith(new_text[:size]):
            return size
    return 0


def _truncation_error(max_tokens: int) -> AITranscriptionError:
    return AITranscriptionError(
        f"工作台 AI 回复达到 max_tokens={max_tokens} 上限，"
        f"连续续写 {MAX_CONTINUATION_ROUNDS} 轮仍未完成。"
        "请在设置中切换输出上限更高的模型，或调大该 provider 的 max_tokens。"
    )


register_chat_provider("openai_compatible", OpenAICompatibleChatProvider)
register_chat_provider("dashscope", OpenAICompatibleChatProvider)
