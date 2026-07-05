"""Agnes 2.0 Flash chat provider for the workbench assistant."""

from __future__ import annotations

from typing import Any

from ._chat import OpenAICompatibleChatProvider
from ..core.registry import register_chat_provider


class AgnesChatProvider(OpenAICompatibleChatProvider):
    """Agnes 2.0 Flash — thinking mode uses nested ``chat_template_kwargs``."""

    def thinking_kwargs(self, enable_thinking: bool | None) -> dict[str, Any]:
        if enable_thinking is None:
            return {}
        return {"chat_template_kwargs": {"enable_thinking": enable_thinking}}


register_chat_provider("agnes", AgnesChatProvider)
