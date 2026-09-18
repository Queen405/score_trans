"""Compatibility imports; implementation lives in the layered package."""

from __future__ import annotations

from .recognition.llm_client import (
    CompletionResult as CompletionResult,
    LlmClient as LlmClient,
    image_to_data_url as image_to_data_url,
)
