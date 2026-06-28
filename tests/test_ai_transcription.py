from __future__ import annotations

from pathlib import Path

from score_trans.api.app import create_app
from score_trans.dao.ai.chat_dao import AiChatDao
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.ai.actions import AiActions
from score_trans.models.ai.schemas import AiTranscribeRequest
from score_trans.models.settings.config import ToolConfig
from score_trans.services.ai.core import VisionPageResult, parse_vision_page_result
from score_trans.services.ai.chat_service import AiChatService, MAX_CONTEXT_MESSAGES
from score_trans.services.ai.providers._http import chat_completions
from score_trans.services.ai.providers.mock import MockVisionJianpuProvider
from score_trans.services.ai.transcription import AiTranscriptionService
from score_trans.services.ai.transcription.validation import validate_jianpu_text
from score_trans.utils.pdf import pdf_to_png_pages
from score_trans.services.files.upload_service import UploadService


class FakeSettings:
    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    def load(self) -> ToolConfig:
        return self.config


def test_ai_transcribe_route_is_registered() -> None:
    paths = set(create_app().openapi()["paths"])
    schema = create_app().openapi()["components"]["schemas"]["AiTranscribeRequest"]

    assert "/ai/transcribe" in paths
    assert "file_id" in schema["properties"]
    assert "render_dpi" in schema["properties"]
    assert schema["properties"]["instrument_profile"]["default"] == "general"


def test_erhu_ai_transcription_injects_profile_prompt_and_metadata(
    tmp_path: Path,
) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.png"
    source.write_bytes(b"fake png")
    file_id = uploads.register(source)
    provider = MockVisionJianpuProvider()
    actions = AiActions(
        uploads=uploads,
        settings=FakeSettings(config),  # type: ignore[arg-type]
        transcriber=AiTranscriptionService(provider),
    )

    response = actions.transcribe_score(
        AiTranscribeRequest(
            file_id=file_id,
            target_key="C",
            instrument_profile="erhu",
        )
    )

    assert provider.prompts
    assert "二胡识别模式" in (provider.prompts[0] or "")
    assert "^lg=拉弓（出弓）" in (provider.prompts[0] or "")
    assert "instrument=erhu" in response.merged_jianpu_text


def test_ai_chat_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])
    schema = create_app().openapi()["components"]["schemas"]["AiChatRequest"]

    assert "/ai/chat" in paths
    assert "/ai/chat/stream" in paths
    assert "/ai/chat/sessions" in paths
    assert "/ai/chat/sessions/{session_id}/messages" in paths
    assert "jianpu_text" in schema["properties"]
    assert "enable_thinking" in schema["properties"]


def test_ai_action_transcribes_uploaded_image_with_mock_provider(
    tmp_path: Path,
) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.png"
    source.write_bytes(b"fake png")
    file_id = uploads.register(source)
    provider = MockVisionJianpuProvider(
        [
            VisionPageResult(
                title="小星星",
                key="C",
                meter="4/4",
                jianpu_text="1=C\n4/4\n1 1 5 5 |",
                measure_number_candidates=[9, 10],
                warnings=["第二小节看不清"],
                confidence=0.86,
            )
        ]
    )
    actions = AiActions(
        uploads=uploads,
        settings=FakeSettings(config),  # type: ignore[arg-type]
        transcriber=AiTranscriptionService(provider),
    )

    response = actions.transcribe_score(
        AiTranscribeRequest(file_id=file_id, target_key="C")
    )

    assert response.pages[0].page_image_file_id == file_id
    assert "1 1 5 5" in response.pages[0].jianpu_text
    assert "1 1 5 5" in uploads.get_path(response.jianpu_file_id).read_text(
        encoding="utf-8"
    )
    assert response.pages[0].measure_number_candidates == [9, 10]
    assert response.pages[0].warnings == ["第二小节看不清"]


def test_ai_action_flags_dotted_duration_prefix_variant(tmp_path: Path) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.png"
    source.write_bytes(b"fake png")
    file_id = uploads.register(source)
    provider = MockVisionJianpuProvider(
        [
            VisionPageResult(
                key="C",
                meter="4/4",
                jianpu_text="1=C\n4/4\nh.4' 1 |",
            )
        ]
    )
    actions = AiActions(
        uploads=uploads,
        settings=FakeSettings(config),  # type: ignore[arg-type]
        transcriber=AiTranscriptionService(provider),
    )

    response = actions.transcribe_score(
        AiTranscribeRequest(file_id=file_id, target_key="C")
    )

    page = response.pages[0]
    # The legacy `h.4'` (dot before degree) is no longer normalized — it is
    # rejected by the parser and surfaced as a validation error instead.
    assert page.jianpu_text == "1=C\n4/4\nh.4' 1 |"
    assert any("附点" in err for err in page.validation_errors)


def test_pdf_to_png_pages_creates_one_png_per_page(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "score.pdf"
    doc = fitz.open()
    for page_no in range(2):
        page = doc.new_page(width=200, height=120)
        page.insert_text((24, 48), f"Page {page_no + 1}")
    doc.save(pdf_path)
    doc.close()

    paths = pdf_to_png_pages(pdf_path, tmp_path / "pages", dpi=72)

    assert len(paths) == 2
    assert all(path.exists() for path in paths)


def test_ai_plain_text_response_falls_back_to_jianpu_text() -> None:
    result = parse_vision_page_result("title=中阮\n1=C\n4/4\n1 2 3 4 |")

    assert result.jianpu_text.startswith("title=中阮")
    assert result.warnings


def test_ai_json_response_accepts_measure_number_candidates() -> None:
    result = parse_vision_page_result(
        {
            "jianpu_text": "1=C\n4/4\n1 2 3 4 |",
            "measure_number_candidates": [17],
            "warnings": [],
        }
    )

    assert result.measure_number_candidates == [17]


def test_ai_validation_applies_accidental_mode() -> None:
    text = "1=C\n4/4\nb7 #4 1 2 |"

    sharp, sharp_errors = validate_jianpu_text(text, accidental_mode="sharp")
    flat, flat_errors = validate_jianpu_text(text, accidental_mode="flat")

    assert sharp_errors == []
    assert flat_errors == []
    assert "#6 #4 1 2 |" in sharp
    assert "b7 b5 1 2 |" in flat


def test_ai_chat_injects_jianpu_syntax_and_limits_memory(
    tmp_path: Path, monkeypatch
) -> None:
    captured_messages = []

    def fake_chat_completions(**kwargs):
        captured_messages.append(kwargs["messages"])
        return "已检查"

    monkeypatch.setattr(
        "score_trans.services.ai.chat_service.chat_completions",
        fake_chat_completions,
    )
    settings = SettingsDao(tmp_path / "settings.db")
    settings.set("assistant_api_key", "test-key")
    settings.set(
        "assistant_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    settings.set("assistant_model", "deepseek-v4-flash")
    service = AiChatService(
        dao=AiChatDao(tmp_path / "ai_chat.db"),
        settings=settings,
    )
    session = service.create_session()
    for index in range(21):
        service.dao.add_message(session.id, "user", f"旧问题 {index}")
        service.dao.add_message(session.id, "assistant", f"旧回答 {index}")

    service.send_message(
        "帮我检查和弦",
        session_id=session.id,
        jianpu_text="1=C\n4/4\n[1,3,5] |",
    )

    messages = captured_messages[-1]
    assert messages[0]["role"] == "system"
    assert "项目简谱语法" in messages[0]["content"]
    assert "[1+3+5]" in messages[0]["content"]
    assert len(messages[1:]) == MAX_CONTEXT_MESSAGES
    assert "【当前工作台简谱文本】" in messages[-1]["content"]
    assert "[1,3,5]" in messages[-1]["content"]


def test_ai_chat_forwards_disabled_thinking_to_provider(
    tmp_path: Path, monkeypatch
) -> None:
    captured_kwargs = []

    def fake_chat_completions(**kwargs):
        captured_kwargs.append(kwargs)
        return "直接回答"

    monkeypatch.setattr(
        "score_trans.services.ai.chat_service.chat_completions",
        fake_chat_completions,
    )
    settings = SettingsDao(tmp_path / "settings.db")
    settings.set("assistant_api_key", "test-key")
    service = AiChatService(
        dao=AiChatDao(tmp_path / "ai_chat.db"),
        settings=settings,
    )

    service.send_message("帮我检查", enable_thinking=False)

    assert captured_kwargs[-1]["enable_thinking"] is False


def test_chat_completions_omits_thinking_param_until_explicitly_set(
    monkeypatch,
) -> None:
    captured_bodies = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(*args, **kwargs):
        captured_bodies.append(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.post",
        fake_post,
    )

    chat_completions(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
    )
    chat_completions(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        enable_thinking=False,
    )

    assert "enable_thinking" not in captured_bodies[0]
    assert captured_bodies[1]["enable_thinking"] is False


def test_ai_chat_stream_persists_streamed_response(tmp_path: Path, monkeypatch) -> None:
    captured_kwargs = []

    def fake_chat_completion_chunks(**kwargs):
        captured_kwargs.append(kwargs)
        yield "<think>检查和弦分隔符</think>"
        yield "\n\n应改为 [1+3+5]。"

    monkeypatch.setattr(
        "score_trans.services.ai.chat_service.chat_completion_chunks",
        fake_chat_completion_chunks,
    )
    settings = SettingsDao(tmp_path / "settings.db")
    settings.set("assistant_api_key", "test-key")
    service = AiChatService(
        dao=AiChatDao(tmp_path / "ai_chat.db"),
        settings=settings,
    )

    events = list(service.stream_message("检查 [1,3,5]", enable_thinking=False))

    assert events[0][0] == "session"
    assert captured_kwargs[-1]["enable_thinking"] is False
    assert ("delta", "<think>检查和弦分隔符</think>") in events
    assert events[-1][0] == "messages"
    messages = events[-1][1]
    assert not isinstance(messages, str)
    assert messages[-1].role == "assistant"
    assert "[1+3+5]" in messages[-1].content
