import base64
import os

import pytest

from score_trans.models.common.errors import OCRError
from score_trans.models.score import OCRTextBlock
from score_trans.services.ocr.parser import parse_openai_compatible_response
from score_trans.services.ocr.providers import MockOCRProvider, OpenAICompatibleOCRProvider
from score_trans.services.ocr.utils import DEFAULT_OCR_MODEL, is_deepseek_ocr_model
from score_trans.services.common.env_file import DISABLE_DOTENV_ENV, load_project_env
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


def test_openai_provider_builds_dry_run_request_without_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
        lambda: {},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")
    provider = OpenAICompatibleOCRProvider(base_url="https://example.test/v1", dry_run=True)

    request = provider.build_request(image)

    assert request.endpoint == "https://example.test/v1/chat/completions"
    assert "Authorization" not in request.headers
    assert "response_format" not in request.payload
    image_url = request.payload["messages"][0]["content"][1]["image_url"]["url"]
    assert image_url == f"data:image/png;base64,{base64.b64encode(b'abc').decode('ascii')}"
    assert provider.recognize(image) == []


def test_openai_provider_reads_api_key_from_environment(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
        lambda: {"ocr_api_key": "test-key"},
    )
    image = tmp_path / "score.jpg"
    image.write_bytes(b"abc")

    request = OpenAICompatibleOCRProvider().build_request(image)

    assert request.headers["Authorization"] == "Bearer test-key"


def test_non_deepseek_ocr_provider_requests_json_response(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
        lambda: {},
    )
    image = tmp_path / "score.jpg"
    image.write_bytes(b"abc")

    request = OpenAICompatibleOCRProvider(model="Qwen/Qwen3-VL-8B-Instruct", dry_run=True).build_request(image)

    assert request.payload["response_format"] == {"type": "json_object"}


def test_openai_provider_reads_persisted_settings(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
        lambda: {
            "ocr_api_key": "persisted-key",
            "ocr_base_url": "https://persisted.example/v1",
            "ocr_model": "Qwen/Qwen3-VL-8B-Instruct",
        },
    )
    image = tmp_path / "score.jpg"
    image.write_bytes(b"abc")

    request = OpenAICompatibleOCRProvider().build_request(image)

    assert request.endpoint == "https://persisted.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer persisted-key"
    assert request.payload["model"] == "Qwen/Qwen3-VL-8B-Instruct"


def test_openai_provider_requires_key_when_not_dry_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
        lambda: {},
    )
    image = tmp_path / "score.png"
    image.write_bytes(b"abc")

    with pytest.raises(OCRError, match="OCR API key"):
        OpenAICompatibleOCRProvider().build_request(image)


def test_default_ocr_model_is_deepseek_ocr(monkeypatch) -> None:
    monkeypatch.setattr(
        "score_trans.services.ocr.utils.persisted_ocr_settings",
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
