from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import time

import pytest

from score_trans.api.app import create_app
from score_trans.dao.ai.chat_dao import AiChatDao
from score_trans.dao.settings.settings_dao import SettingsDao
from score_trans.exec.ai.actions import AiActions
from score_trans.models.ai.schemas import AiTranscribeRequest
from score_trans.models.common.errors import AITranscriptionError
from score_trans.models.settings.config import ToolConfig
from score_trans.services.ai.core import VisionPageResult, parse_vision_page_result
from score_trans.services.ai.core import prompts as prompt_config
from score_trans.services.ai.chat_service import AiChatService, MAX_CONTEXT_MESSAGES
from score_trans.services.ai.providers._http import (
    chat_completion_chunks,
    chat_completions,
)
from score_trans.services.ai.providers._vision import (
    OpenAICompatibleVisionTranscriber,
)
from score_trans.services.ai.providers.dashscope import DashScopeVisionProvider
from score_trans.services.ai.providers.mock import MockVisionJianpuProvider
from score_trans.services.ai.providers.openai_compatible import (
    OpenAICompatibleVisionProvider,
)
from score_trans.services.ai.providers.xiaomi_mimo import XiaomiMiMoProvider
from score_trans.services.ai.transcription import AiTranscriptionService
from score_trans.services.ai.transcription.validation import validate_jianpu_text
from score_trans.utils.pdf import pdf_to_png_pages
from score_trans.services.files.upload_service import UploadService


class FakeSettings:
    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    def load(self) -> ToolConfig:
        return self.config


class CapturingTranscriber:
    def __init__(self) -> None:
        self.render_dpi: int | None = None

    def transcribe(self, *args, render_dpi: int, **kwargs):
        self.render_dpi = render_dpi
        raise RuntimeError("capture complete")


@pytest.mark.parametrize(
    "provider_class",
    [
        OpenAICompatibleVisionProvider,
        DashScopeVisionProvider,
        XiaomiMiMoProvider,
    ],
)
def test_vision_providers_share_one_transcription_implementation(
    provider_class,
) -> None:
    assert issubclass(provider_class, OpenAICompatibleVisionTranscriber)
    assert (
        provider_class.transcribe_page
        is OpenAICompatibleVisionTranscriber.transcribe_page
    )


def test_empty_ai_prompt_yaml_reports_missing_required_field(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "ai_prompt.yaml").write_text("", encoding="utf-8")
    previous = prompt_config._PROMPT_CONFIG
    monkeypatch.setattr(prompt_config, "CONFIG_DIR", tmp_path)
    prompt_config._PROMPT_CONFIG = None
    try:
        with pytest.raises(AITranscriptionError, match="prompt_template"):
            prompt_config.build_jianpu_prompt(
                target_key="C",
                title=None,
                page_index=0,
                extra_prompt=None,
            )
    finally:
        prompt_config._PROMPT_CONFIG = previous


def test_ai_transcribe_route_is_registered() -> None:
    paths = set(create_app().openapi()["paths"])
    schema = create_app().openapi()["components"]["schemas"]["AiTranscribeRequest"]

    assert "/ai/transcribe" in paths
    assert "file_id" in schema["properties"]
    assert "render_dpi" in schema["properties"]
    assert schema["properties"]["instrument_profile"]["default"] == "general"


@pytest.mark.parametrize(
    ("requested_dpi", "expected_dpi"),
    [(None, 271), (320, 320)],
)
def test_ai_actions_injects_render_dpi_at_execution_boundary(
    tmp_path: Path,
    requested_dpi: int | None,
    expected_dpi: int,
) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "score.png"
    source.write_bytes(b"fake png")
    transcriber = CapturingTranscriber()
    actions = AiActions(
        uploads=uploads,
        settings=FakeSettings(config),  # type: ignore[arg-type]
        transcriber=transcriber,  # type: ignore[arg-type]
        default_render_dpi=271,
    )

    with pytest.raises(RuntimeError, match="capture complete"):
        actions.transcribe_score(
            AiTranscribeRequest(
                file_id=uploads.register(source),
                render_dpi=requested_dpi,
            )
        )

    assert transcriber.render_dpi == expected_dpi


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


def test_guzheng_ai_transcription_injects_catalog_and_metadata(
    tmp_path: Path,
) -> None:
    config = ToolConfig(work_dir=tmp_path / "work")
    uploads = UploadService(config)
    source = tmp_path / "guzheng.png"
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
            instrument_profile="guzheng",
        )
    )

    prompt = provider.prompts[0] or ""
    assert "古筝识别模式" in prompt
    assert "^l=摇指" in prompt
    assert "^sy=扫摇" in prompt
    assert "^st=双托" in prompt
    assert "双托、双抹和琶音后必须是和弦" in prompt
    assert "instrument=guzheng" in response.merged_jianpu_text


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


def test_pdf_to_png_pages_distinguishes_zero_from_no_limit(tmp_path: Path) -> None:
    import fitz

    pdf_path = tmp_path / "score.pdf"
    doc = fitz.open()
    doc.new_page(width=200, height=120)
    doc.new_page(width=200, height=120)
    doc.save(pdf_path)
    doc.close()

    assert pdf_to_png_pages(pdf_path, tmp_path / "none", dpi=72, max_pages=0) == []
    assert len(pdf_to_png_pages(pdf_path, tmp_path / "one", dpi=72, max_pages=1)) == 1
    assert (
        len(pdf_to_png_pages(pdf_path, tmp_path / "all", dpi=72, max_pages=None)) == 2
    )


def test_pdf_to_png_pages_rejects_negative_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_pages"):
        pdf_to_png_pages(
            tmp_path / "not-opened.pdf",
            tmp_path / "pages",
            dpi=72,
            max_pages=-1,
        )

    assert not (tmp_path / "pages").exists()


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


def test_chat_completions_reports_empty_choices(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": []}

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="choices"):
        chat_completions(
            base_url="https://example.test/v1",
            api_key="test-key",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_chat_completion_chunks_ignores_usage_only_empty_choices(
    monkeypatch,
) -> None:
    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(
                [
                    'data: {"choices":[],"usage":{"total_tokens":3}}',
                    'data: {"choices":[{"delta":{"content":"ok"}}]}',
                    "data: [DONE]",
                ]
            )

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.stream",
        lambda *args, **kwargs: FakeStreamResponse(),
    )

    chunks = list(
        chat_completion_chunks(
            base_url="https://example.test/v1",
            api_key="test-key",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
        )
    )

    assert chunks == ["ok"]


def test_chat_completion_chunks_surfaces_provider_error_payload(
    monkeypatch,
) -> None:
    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            return iter(['data: {"error":{"message":"quota exceeded"}}'])

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.stream",
        lambda *args, **kwargs: FakeStreamResponse(),
    )

    with pytest.raises(RuntimeError, match="quota exceeded"):
        list(
            chat_completion_chunks(
                base_url="https://example.test/v1",
                api_key="test-key",
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
            )
        )


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


def test_ai_chat_stream_failure_does_not_persist_orphan_user_message(
    tmp_path: Path, monkeypatch
) -> None:
    def failing_chunks(**kwargs):
        yield "已生成一部分"
        raise RuntimeError("provider disconnected")

    monkeypatch.setattr(
        "score_trans.services.ai.chat_service.chat_completion_chunks",
        failing_chunks,
    )
    settings = SettingsDao(tmp_path / "settings.db")
    settings.set("assistant_api_key", "test-key")
    dao = AiChatDao(tmp_path / "ai_chat.db")
    service = AiChatService(dao=dao, settings=settings)
    stream = service.stream_message("这条消息不能成为孤立记录")

    event, session_id = next(stream)
    assert event == "session"
    assert next(stream) == ("delta", "已生成一部分")
    with pytest.raises(AITranscriptionError, match="provider disconnected"):
        next(stream)

    assert isinstance(session_id, str)
    assert dao.list_messages(session_id) == []


def test_ai_chat_non_stream_failure_does_not_persist_orphan_user_message(
    tmp_path: Path, monkeypatch
) -> None:
    def failing_completion(**kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "score_trans.services.ai.chat_service.chat_completions",
        failing_completion,
    )
    settings = SettingsDao(tmp_path / "settings.db")
    settings.set("assistant_api_key", "test-key")
    dao = AiChatDao(tmp_path / "ai_chat.db")
    service = AiChatService(dao=dao, settings=settings)
    session = service.create_session("保留标题")

    with pytest.raises(AITranscriptionError, match="provider unavailable"):
        service.send_message("不要落库", session_id=session.id)

    assert dao.list_messages(session.id) == []
    assert dao.get_session(session.id).title == "保留标题"


def test_ai_chat_exchange_is_committed_atomically(tmp_path: Path) -> None:
    dao = AiChatDao(tmp_path / "ai_chat.db")
    session = dao.create_session("session-1")
    with sqlite3.connect(dao.db_path) as conn:
        conn.execute(
            """
            CREATE TRIGGER reject_assistant_message
            BEFORE INSERT ON ai_chat_message
            WHEN NEW.role = 'assistant'
            BEGIN
                SELECT RAISE(ABORT, 'assistant rejected');
            END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="assistant rejected"):
        dao.add_exchange(
            session.id,
            user_content="用户消息",
            assistant_content="助手消息",
            title_if_empty="首轮标题",
        )

    assert dao.list_messages(session.id) == []
    assert dao.get_session(session.id).title == "新对话"


def test_ai_chat_dao_accepts_system_messages(tmp_path: Path) -> None:
    dao = AiChatDao(tmp_path / "ai_chat.db")
    session = dao.create_session("session-system")

    message = dao.add_message(session.id, "system", "项目级系统提示")

    assert message.role == "system"
    assert dao.list_messages(session.id) == [message]


def test_ai_chat_dao_migrates_legacy_role_constraint_without_data_loss(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-ai-chat.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE ai_chat_session (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE ai_chat_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES ai_chat_session(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            INSERT INTO ai_chat_session (id, title) VALUES ('legacy', '旧会话');
            INSERT INTO ai_chat_message (session_id, role, content)
            VALUES ('legacy', 'user', '保留的旧消息');
            """
        )

    dao = AiChatDao(db_path)
    system = dao.add_message("legacy", "system", "迁移后的系统消息")

    messages = dao.list_messages("legacy")
    assert [(item.role, item.content) for item in messages] == [
        ("user", "保留的旧消息"),
        ("system", "迁移后的系统消息"),
    ]
    assert system.id > messages[0].id


def test_ai_chat_connections_enable_wal_and_busy_timeout(tmp_path: Path) -> None:
    dao = AiChatDao(tmp_path / "ai_chat.db")

    with dao._connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert busy_timeout == 5000


def test_ai_chat_write_waits_for_a_short_database_lock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dao = AiChatDao(tmp_path / "ai_chat.db")
    session = dao.create_session("session-lock")
    real_connect = sqlite3.connect

    def connect_without_default_wait(*args, **kwargs):
        kwargs["timeout"] = 0
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(
        "score_trans.dao.ai.chat_dao.sqlite3.connect",
        connect_without_default_wait,
    )

    lock_conn = real_connect(dao.db_path, timeout=0)
    try:
        lock_conn.execute("BEGIN IMMEDIATE")
        lock_conn.execute(
            "UPDATE ai_chat_session SET title = title WHERE id = ?",
            (session.id,),
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                dao.add_message,
                session.id,
                "user",
                "等待短暂写锁",
            )
            time.sleep(0.05)
            assert not future.done()
            lock_conn.commit()
            message = future.result(timeout=2)
    finally:
        lock_conn.close()

    assert message.content == "等待短暂写锁"
