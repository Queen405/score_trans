from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .schemas import VisionPageResult


@runtime_checkable
class VisionJianpuProvider(Protocol):
    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        """Return one page of score transcription as project Jianpu syntax."""


@runtime_checkable
class ChatProvider(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool | None = None,
    ) -> str:
        """Send messages and return the assistant's response content."""

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        enable_thinking: bool | None = None,
    ) -> Iterator[str]:
        """Stream text chunks from the assistant's response."""
