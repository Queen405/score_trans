from __future__ import annotations

from pathlib import Path

from ..core.registry import register_provider
from ..core.schemas import VisionPageResult


class MockVisionJianpuProvider:
    def __init__(self, results: list[VisionPageResult] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[Path] = []
        self.prompts: list[str | None] = []

    def transcribe_page(
        self,
        image_path: str | Path,
        *,
        target_key: str = "C",
        title: str | None = None,
        page_index: int = 0,
        extra_prompt: str | None = None,
    ) -> VisionPageResult:
        self.calls.append(Path(image_path))
        self.prompts.append(extra_prompt)
        if self.results:
            return self.results[min(page_index, len(self.results) - 1)]
        return VisionPageResult(
            title=title,
            key=target_key,
            meter="4/4",
            jianpu_text=f"title={title or 'AI 简谱'}\n1={target_key}\n4/4\n1 2 3 4 |",
            warnings=[],
            confidence=1.0,
        )


register_provider("mock", MockVisionJianpuProvider)
