import os
from unittest.mock import MagicMock, patch

import pytest

from score_trans.models.common.errors import OCRError
from score_trans.models.score import OCRTextBlock
from score_trans.services.ocr.parsing import parse_openai_compatible_response
from score_trans.services.ocr.providers import MockOCRProvider, OpenAICompatibleOCRProvider
from score_trans.services.ocr.core import DEFAULT_OCR_MODEL, is_deepseek_ocr_model
from score_trans.utils.env import load_project_env
from score_trans.services.ocr.service import OCRService


def test_mock_provider_feeds_text_layer(tmp_path) -> None:
    image = tmp_path / "score.png"
    image.write_bytes(b"fake image")
    provider = MockOCRProvider(
        [OCRTextBlock("Allegro", bbox=(1, 2, 3, 4), confidence=0.9, role="expression")]
    )

    layer = OCRService(provider).extract_text_layer(image)

    assert layer.plain_text == "Allegro"
    assert layer.blocks[0].bbox == (1, 2, 3, 4)
    assert provider.calls == [image]


def test_ocr_provider_dry_run_returns_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")
    provider = OpenAICompatibleOCRProvider(dry_run=True)
    assert provider.recognize(image) == []


def test_ocr_provider_requires_api_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")
    provider = OpenAICompatibleOCRProvider()
    with pytest.raises(OCRError, match="OCR API key"):
        provider.recognize(image)


def test_ocr_provider_invokes_langchain_with_correct_params(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {"ocr_api_key": "test-key"},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"text_blocks":[{"text":"A","role":"other"}]}'}}]
    }

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        provider = OpenAICompatibleOCRProvider(base_url="https://example.test/v1", model="Qwen/Qwen3-VL-8B-Instruct")
        blocks = provider.recognize(image)

    mock_post.assert_called_once()
    assert blocks[0].text == "A"


def test_ocr_provider_json_object_for_non_deepseek(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {"ocr_api_key": "test-key"},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": '{"text_blocks":[]}'}}]
    }

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        provider = OpenAICompatibleOCRProvider(model="Qwen/Qwen3-VL-8B-Instruct")
        provider.recognize(image)

    _, kwargs = mock_post.call_args
    body = kwargs["json"]
    assert body["response_format"] == {"type": "json_object"}


def test_ocr_provider_fallback_on_useless_blocks(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {
            "ocr_api_key": "test-key",
            "ocr_model": "deepseek-ai/DeepSeek-OCR",
            "ocr_fallback_model": "Qwen/Qwen3-VL-8B-Instruct",
        },
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")

    call_count = 0

    def fake_post(url, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        if call_count == 1:
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": '{"text_blocks":[]}'}}]
            }
        else:
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": '{"text_blocks":[{"text":"A","role":"other"}]}'}}]
            }
        return mock_resp

    with patch("httpx.post", side_effect=fake_post):
        provider = OpenAICompatibleOCRProvider()
        blocks = provider.recognize(image)

    assert len(blocks) == 1
    assert blocks[0].text == "A"


def test_default_ocr_model_is_deepseek_ocr(monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.core.persisted_ocr_settings",
        lambda: {},
    )

    provider = OpenAICompatibleOCRProvider(dry_run=True)

    assert DEFAULT_OCR_MODEL == "deepseek-ai/DeepSeek-OCR"
    assert provider.model == "deepseek-ai/DeepSeek-OCR"
    assert is_deepseek_ocr_model(provider.model)


def test_project_env_loader_populates_missing_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SCORE_TRANS_OCR_BASE_URL=https://example.test/v1\n"
        "SCORE_TRANS_OCR_MODEL='deepseek-ai/DeepSeek-OCR'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SCORE_TRANS_OCR_BASE_URL", raising=False)
    monkeypatch.delenv("SCORE_TRANS_OCR_MODEL", raising=False)

    load_project_env(env_file)

    assert os.environ["SCORE_TRANS_OCR_BASE_URL"] == "https://example.test/v1"
    assert os.environ["SCORE_TRANS_OCR_MODEL"] == "deepseek-ai/DeepSeek-OCR"


def test_parse_openai_compatible_response_coerces_blocks() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"text_blocks":[{"text":"Title","bbox":[0,1,2,3],'
                        '"confidence":"0.95","role":"title"},'
                        '{"text":"118"},'
                        '{"text":"?","role":"unknown"}]}'
                    )
                }
            }
        ]
    }

    blocks = parse_openai_compatible_response(response)

    assert blocks == [
        OCRTextBlock("Title", bbox=(0.0, 1.0, 2.0, 3.0), confidence=0.95, role="title"),
        OCRTextBlock("118", role="measure_number"),
        OCRTextBlock("?", role="other"),
    ]


def test_parse_openai_compatible_response_accepts_common_bbox_aliases() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"result":{"items":['
                        '{"content":"Allegro","bbox_2d":[[10,20],[80,20],[80,44],[10,44]],"type":"tempo"},'
                        '{"label":"7","box":{"x":1,"y":2,"w":3,"h":4},"type":"bar_number"}'
                        "]}}"
                    )
                }
            }
        ]
    }

    blocks = parse_openai_compatible_response(response)

    assert blocks == [
        OCRTextBlock("Allegro", bbox=(10.0, 20.0, 80.0, 44.0), role="expression"),
        OCRTextBlock("7", bbox=(1.0, 2.0, 4.0, 6.0), role="measure_number"),
    ]


def test_parse_openai_compatible_response_accepts_plain_text() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "content": (
                        "2. Title: Spring Song\n"
                        "Allegro 1=CAllegro 1=CThe text in the image is black on white.\n"
                        "The text reads:\n"
                        "Title: Spring Song\n"
                        "Allegro 1=C"
                    )
                }
            }
        ]
    }

    blocks = parse_openai_compatible_response(response)

    assert [block.text for block in blocks] == ["Title: Spring Song", "Allegro 1=C"]
    assert blocks[1].role == "expression"


def test_parse_openai_compatible_response_accepts_json_list() -> None:
    response = {"choices": [{"message": {"content": '["Title", "Allegro"]'}}]}

    blocks = parse_openai_compatible_response(response)

    assert [block.text for block in blocks] == ["Title", "Allegro"]
