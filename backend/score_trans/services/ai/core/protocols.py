from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

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
