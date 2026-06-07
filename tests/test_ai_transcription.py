from __future__ import annotations

from pathlib import Path

from score_trans.api.app import create_app
from score_trans.dao.ai.chat_dao import AiChatDao
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.ai.actions import AiActions
from score_trans.models.ai.schemas import AiTranscribeRequest
from score_trans.models.settings.config import ToolConfig
from score_trans.services.ai.base import VisionPageResult, parse_vision_page_result
from score_trans.services.ai.chat_service import AiChatService, MAX_CONTEXT_MESSAGES
from score_trans.services.ai.providers.mock import MockVisionJianpuProvider
from score_trans.services.ai.service import AiTranscriptionService, ensure_jianpu_header
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


def test_ai_chat_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])
    schema = create_app().openapi()["components"]["schemas"]["AiChatRequest"]

    assert "/ai/chat" in paths
    assert "/ai/chat/sessions" in paths
    assert "/ai/chat/sessions/{session_id}/messages" in paths
    assert "jianpu_text" in schema["properties"]


def test_ai_action_transcribes_uploaded_image_with_mock_provider(tmp_path: Path) -> None:
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

    response = actions.transcribe_score(AiTranscribeRequest(file_id=file_id, target_key="C"))

    assert response.pages[0].page_image_file_id == file_id
    assert "1 1 5 5" in response.pages[0].jianpu_text
    assert "1 1 5 5" in uploads.get_path(response.jianpu_file_id).read_text(encoding="utf-8")
    assert response.pages[0].warnings == ["第二小节看不清"]


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


def test_ai_header_cleanup_ignores_legacy_field_values() -> None:
    text = ensure_jianpu_header(
        "1 2 3 4 |",
        target_key="key=G",
        meter="time=3/4",
        title=None,
    )

    assert text.startswith("1=C\n4/4\n")


def test_ai_plain_text_response_falls_back_to_jianpu_text() -> None:
    result = parse_vision_page_result("title=中阮\n1=C\n4/4\n1 2 3 4 |")

    assert result.jianpu_text.startswith("title=中阮")
    assert result.warnings


def test_ai_chat_injects_jianpu_syntax_and_limits_memory(tmp_path: Path, monkeypatch) -> None:
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
    settings.set("assistant_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
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
