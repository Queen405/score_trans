from __future__ import annotations

from .mock import MockOCRProvider
from .openai_compatible import OpenAICompatibleOCRProvider

__all__ = ["MockOCRProvider", "OpenAICompatibleOCRProvider"]
