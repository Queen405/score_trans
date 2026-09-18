from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def synthetic_jianpu_image(tmp_path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default(size=24)
    except TypeError:
        font = ImageFont.load_default()
    draw.text((50, 20), "1=C  4/4", fill="black", font=font)
    draw.text((50, 100), "1 2 3 4 | 5 6 7 1' |", fill="black", font=font)
    draw.text((50, 200), "2 3 4 5 | 6 7 1' 2' |", fill="black", font=font)
    path = tmp_path / "sample.png"
    img.save(path)
    return path


@pytest.fixture
def mock_llm_response() -> str:
    return json.dumps(
        {
            "row_type": "notation",
            "row_text": "1 2 3 4 |",
            "tokens": [
                {"text": "1", "x": 0.05, "w": 0.04, "role": "note"},
                {"text": "2", "x": 0.12, "w": 0.04, "role": "note"},
                {"text": "3", "x": 0.19, "w": 0.04, "role": "note"},
                {"text": "4", "x": 0.26, "w": 0.04, "role": "note"},
                {"text": "|", "x": 0.33, "w": 0.02, "role": "barline"},
            ],
            "warnings": [],
            "confidence": 0.9,
        }
    )


class MockLlmClient:
    def __init__(self, response: str):
        self._response = response
        self.calls: list[tuple[Path, str]] = []

    def transcribe_row_with_retry(self, image_path, prompt, **kwargs):
        self.calls.append((image_path, prompt))
        from trans_jp.llm_client import CompletionResult

        return CompletionResult(content=self._response, finish_reason="stop")


@pytest.fixture
def mock_llm_client(mock_llm_response) -> MockLlmClient:
    return MockLlmClient(mock_llm_response)
