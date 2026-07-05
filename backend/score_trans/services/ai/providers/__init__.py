from __future__ import annotations

# Import sub-modules to auto-register providers in the global registry.
from . import agnes, dashscope, mock, openai_compatible, sensenova, xiaomi_mimo
from . import _chat  # noqa: F401 — registers "openai_compatible"/"dashscope" chat providers

__all__ = [
    "agnes",
    "dashscope",
    "mock",
    "openai_compatible",
    "sensenova",
    "xiaomi_mimo",
]
