"""Tests for workbench chat continuation and vision compact retry.

Covers:
- finish_reason parsing (non-stream and stream) including missing finish_reason
- limited-round automatic continuation for chat (stream and non-stream)
- repetition / no-new-content abort
- provider-profile-aware max_tokens resolution and validation
- vision truncation retry with a compact prompt (no JSON concatenation)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image
from score_trans import __file__ as _package_file
from score_trans.config.settings import ASSISTANT_MAX_TOKENS
from score_trans.models.common.errors import AITranscriptionError
from score_trans.models.settings.provider_profiles import LlmProviderProfile
from score_trans.services.ai.core import prompts as prompt_config
from score_trans.services.ai.providers._chat import (
    MAX_CONTINUATION_ROUNDS,
    OpenAICompatibleChatProvider,
    continuation_messages,
)
from score_trans.services.ai.providers._http import (
    CompletionResult,
    StreamChunk,
    chat_completion_chunks,
    chat_completions,
)
from score_trans.services.ai.providers.openai_compatible import (
    OpenAICompatibleVisionProvider,
)
from score_trans.services.settings import provider_profiles as profiles_module
from score_trans.services.settings.provider_profiles import _parse_profiles

_REAL_CONFIG_DIR = Path(_package_file).parent / "config"
_MESSAGES = [{"role": "user", "content": "写一段长回答"}]


class HttpStub:
    """Sequential chat_completions results, capturing each request."""

    def __init__(self, results: list[CompletionResult]) -> None:
        self.results = list(results)
        self.requests: list[dict] = []

    def __call__(self, *, messages, **kwargs) -> CompletionResult:
        self.requests.append({"messages": messages, **kwargs})
        if not self.results:
            raise AssertionError("unexpected extra chat_completions call")
        return self.results.pop(0)


def _provider() -> OpenAICompatibleChatProvider:
    return OpenAICompatibleChatProvider(
        base_url="https://example.test/v1",
        model="test-model",
        api_key="test-key",
    )


# ---------------------------------------------------------------------------
# finish_reason parsing (HTTP layer)
# ---------------------------------------------------------------------------


def test_chat_completions_returns_finish_reason(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": "半截"}, "finish_reason": "length"}]
            }

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    result = chat_completions(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
        messages=_MESSAGES,
    )

    assert result.content == "半截"
    assert result.finish_reason == "length"


def test_chat_completions_tolerates_missing_finish_reason(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": "回答"}}]}

    monkeypatch.setattr(
        "score_trans.services.ai.providers._http.httpx.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    result = chat_completions(
        base_url="https://example.test/v1",
        api_key="test-key",
        model="test-model",
        messages=_MESSAGES,
    )

    assert result.content == "回答"
    assert result.finish_reason is None


def test_chat_completion_chunks_reports_final_finish_reason(monkeypatch) -> None:
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
                    'data: {"choices":[{"delta":{"content":"片段"},"finish_reason":null}]}',
                    'data: {"choices":[{"delta":{},"finish_reason":"length"}]}',
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
            messages=_MESSAGES,
        )
    )

    assert [chunk.text for chunk in chunks] == ["片段", ""]
    assert chunks[-1].finish_reason == "length"


# ---------------------------------------------------------------------------
# non-stream continuation
# ---------------------------------------------------------------------------


def test_chat_continues_when_finish_reason_is_length(monkeypatch) -> None:
    stub = HttpStub(
        [
            CompletionResult("第一段", "length"),
            CompletionResult("第二段", "stop"),
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    assert _provider().chat(_MESSAGES) == "第一段第二段"

    assert len(stub.requests) == 2
    first_messages = stub.requests[0]["messages"]
    second_messages = stub.requests[1]["messages"]
    assert first_messages == _MESSAGES
    assert second_messages[: len(_MESSAGES)] == _MESSAGES
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["content"] == "第一段"
    assert second_messages[-1]["role"] == "user"
    assert "继续" in second_messages[-1]["content"]


def test_chat_treats_missing_finish_reason_as_complete(monkeypatch) -> None:
    stub = HttpStub([CompletionResult("一次性回答")])
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    assert _provider().chat(_MESSAGES) == "一次性回答"
    assert len(stub.requests) == 1


def test_chat_raises_when_continuation_rounds_exhausted(monkeypatch) -> None:
    stub = HttpStub(
        [
            CompletionResult(f"第 {index} 段", "length")
            for index in range(MAX_CONTINUATION_ROUNDS + 1)
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    with pytest.raises(AITranscriptionError, match="max_tokens"):
        _provider().chat(_MESSAGES)

    assert len(stub.requests) == MAX_CONTINUATION_ROUNDS + 1


def test_chat_aborts_when_continuation_repeats(monkeypatch) -> None:
    stub = HttpStub(
        [
            CompletionResult("1 2 3 4 |", "length"),
            CompletionResult("1 2 3 4 |", "stop"),
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    with pytest.raises(AITranscriptionError, match="重复"):
        _provider().chat(_MESSAGES)


def test_chat_aborts_when_continuation_overlaps_previous_tail(monkeypatch) -> None:
    repeated = "重复片段" * 12  # 48 chars，超过最小重叠阈值
    stub = HttpStub(
        [
            CompletionResult(f"前半部分 {repeated}", "length"),
            CompletionResult(f"{repeated} 新内容", "stop"),
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    with pytest.raises(AITranscriptionError, match="重复"):
        _provider().chat(_MESSAGES)


def test_chat_aborts_when_continuation_adds_nothing(monkeypatch) -> None:
    stub = HttpStub(
        [
            CompletionResult("前半段", "length"),
            CompletionResult("", "stop"),
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completions", stub
    )

    with pytest.raises(AITranscriptionError, match="未产生新内容"):
        _provider().chat(_MESSAGES)


# ---------------------------------------------------------------------------
# stream continuation
# ---------------------------------------------------------------------------


class StreamStub:
    """Sequential per-round chunk sequences, capturing each request."""

    def __init__(self, rounds: list[list[StreamChunk]]) -> None:
        self.rounds = list(rounds)
        self.requests: list[dict] = []

    def __call__(self, *, messages, **kwargs):
        self.requests.append({"messages": messages, **kwargs})
        if not self.rounds:
            raise AssertionError("unexpected extra chat_completion_chunks call")
        return iter(self.rounds.pop(0))


def test_stream_chat_continues_after_length(monkeypatch) -> None:
    stub = StreamStub(
        [
            [StreamChunk("第一段", "length")],
            [StreamChunk("第二段"), StreamChunk("", "stop")],
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completion_chunks", stub
    )

    text = "".join(_provider().stream_chat(_MESSAGES))

    assert text == "第一段第二段"
    assert len(stub.requests) == 2
    second_messages = stub.requests[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["content"] == "第一段"


def test_stream_chat_completes_without_finish_reason(monkeypatch) -> None:
    stub = StreamStub([[StreamChunk("回答"), StreamChunk("", None)]])
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completion_chunks", stub
    )

    assert "".join(_provider().stream_chat(_MESSAGES)) == "回答"
    assert len(stub.requests) == 1


def test_stream_chat_raises_when_continuation_exhausted(monkeypatch) -> None:
    stub = StreamStub(
        [
            [StreamChunk(f"第 {index} 段", "length")]
            for index in range(MAX_CONTINUATION_ROUNDS + 1)
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completion_chunks", stub
    )

    with pytest.raises(AITranscriptionError, match="max_tokens"):
        list(_provider().stream_chat(_MESSAGES))

    assert len(stub.requests) == MAX_CONTINUATION_ROUNDS + 1


def test_stream_chat_aborts_when_continuation_repeats(monkeypatch) -> None:
    stub = StreamStub(
        [
            [StreamChunk("旧内容", "length")],
            [StreamChunk("旧内容"), StreamChunk("", "stop")],
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completion_chunks", stub
    )

    with pytest.raises(AITranscriptionError, match="重复"):
        list(_provider().stream_chat(_MESSAGES))


def test_stream_chat_continuation_strips_think_blocks(monkeypatch) -> None:
    stub = StreamStub(
        [
            [
                StreamChunk("<think>推理过程</think>\n\n"),
                StreamChunk("正文", "length"),
            ],
            [StreamChunk("续写"), StreamChunk("", "stop")],
        ]
    )
    monkeypatch.setattr(
        "score_trans.services.ai.providers._chat.chat_completion_chunks", stub
    )

    text = "".join(_provider().stream_chat(_MESSAGES))

    assert text == "<think>推理过程</think>\n\n正文续写"
    second_messages = stub.requests[1]["messages"]
    assert second_messages[-2]["content"] == "正文"


# ---------------------------------------------------------------------------
# continuation message building
# ---------------------------------------------------------------------------


def test_continuation_messages_strip_think_blocks() -> None:
    result = continuation_messages(_MESSAGES, ["<think>x</think>\n\n答案"])
    assert result[-2]["content"] == "答案"


def test_continuation_messages_keep_raw_text_when_only_thinking() -> None:
    result = continuation_messages(_MESSAGES, ["<think>还在思考"])
    assert result[-2]["content"] == "<think>还在思考"


def test_continuation_messages_passthrough_first_round() -> None:
    assert continuation_messages(_MESSAGES, []) == _MESSAGES


# ---------------------------------------------------------------------------
# provider profile max_tokens
# ---------------------------------------------------------------------------


def _inject_profiles(
    monkeypatch,
    kind: str,
    profiles: list[LlmProviderProfile],
    default_id: str,
) -> None:
    all_profiles = dict(profiles_module._PROFILES)
    all_profiles[kind] = tuple(profiles)
    monkeypatch.setattr(profiles_module, "_PROFILES", all_profiles)
    defaults = dict(profiles_module._DEFAULTS)
    defaults[kind] = default_id
    monkeypatch.setattr(profiles_module, "_DEFAULTS", defaults)


def _profile(**overrides) -> LlmProviderProfile:
    values = {
        "id": "test_profile",
        "label": "Test",
        "provider": "openai_compatible",
        "base_url": "https://example.test/v1",
        "model": "test-model",
    }
    values.update(overrides)
    return LlmProviderProfile(**values)


def test_chat_provider_max_tokens_prefers_profile(monkeypatch) -> None:
    _inject_profiles(
        monkeypatch, "assistant", [_profile(max_tokens=8192)], "test_profile"
    )

    provider = OpenAICompatibleChatProvider(api_key="test-key")

    assert provider.max_tokens == 8192


def test_chat_provider_max_tokens_falls_back_to_env(monkeypatch) -> None:
    _inject_profiles(monkeypatch, "assistant", [_profile()], "test_profile")

    provider = OpenAICompatibleChatProvider(api_key="test-key")

    assert provider.max_tokens == ASSISTANT_MAX_TOKENS


def test_vision_provider_max_tokens_prefers_matching_profile(monkeypatch) -> None:
    _inject_profiles(monkeypatch, "ai", [_profile(max_tokens=8192)], "test_profile")

    provider = OpenAICompatibleVisionProvider(api_key="test-key")

    assert provider.max_tokens == 8192


def test_vision_provider_ignores_mismatched_profile_tokens(monkeypatch) -> None:
    _inject_profiles(
        monkeypatch,
        "ai",
        [_profile(provider="xiaomi_mimo", max_tokens=8192)],
        "test_profile",
    )

    provider = OpenAICompatibleVisionProvider(api_key="test-key")

    assert provider.max_tokens == 0


@pytest.mark.parametrize("bad_value", [0, -1, "8192", 1.5, True])
def test_profile_rejects_invalid_max_tokens(bad_value) -> None:
    raw = json.dumps(
        [
            {
                "id": "p",
                "label": "P",
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "model": "m",
                "max_tokens": bad_value,
            }
        ]
    )

    with pytest.raises(ValueError, match="max_tokens"):
        _parse_profiles("TEST_PROVIDER_PROFILES", raw)


def test_profile_accepts_valid_max_tokens() -> None:
    raw = json.dumps(
        [
            {
                "id": "p",
                "label": "P",
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "model": "m",
                "max_tokens": 8192,
            }
        ]
    )

    profiles = _parse_profiles("TEST_PROVIDER_PROFILES", raw)

    assert profiles[0].max_tokens == 8192


def test_profile_without_max_tokens_defaults_to_zero() -> None:
    raw = json.dumps(
        [
            {
                "id": "p",
                "label": "P",
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "model": "m",
            }
        ]
    )

    profiles = _parse_profiles("TEST_PROVIDER_PROFILES", raw)

    assert profiles[0].max_tokens == 0


# ---------------------------------------------------------------------------
# vision compact retry
# ---------------------------------------------------------------------------


class FakePostResponse:
    def __init__(self, content: str, finish_reason: str | None) -> None:
        self._payload = {
            "choices": [
                {"message": {"content": content}, "finish_reason": finish_reason}
            ]
        }

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def real_prompt_config(monkeypatch):
    """Point prompt config at the repository config and reset its cache."""
    monkeypatch.setattr(prompt_config, "CONFIG_DIR", _REAL_CONFIG_DIR)
    monkeypatch.setattr(prompt_config, "_PROMPT_CONFIG", None)


@pytest.fixture
def score_image(tmp_path: Path) -> Path:
    image = tmp_path / "page.png"
    Image.new("RGB", (24, 24), "white").save(image)
    return image


def _install_post(monkeypatch, responses: list[FakePostResponse]) -> list[dict]:
    captured: list[dict] = []

    def fake_post(
        url,
        json: dict | None = None,
        headers=None,
        timeout=None,
    ):
        assert json is not None
        captured.append(json)
        return responses.pop(0)

    monkeypatch.setattr("score_trans.services.ai.providers._http.httpx.post", fake_post)
    return captured


def test_vision_retries_with_compact_prompt_when_truncated(
    monkeypatch, tmp_path: Path, real_prompt_config, score_image: Path
) -> None:
    captured = _install_post(
        monkeypatch,
        [
            FakePostResponse('{"jianpu_text": "1=C\\n4/4\\n1 2 |', "length"),
            FakePostResponse(
                '{"jianpu_text":"1=C\\n4/4\\n1 2 3 4 |","title":null,"key":"C","meter":"4/4"}',
                "stop",
            ),
        ],
    )

    provider = OpenAICompatibleVisionProvider(api_key="test-key")
    result = provider.transcribe_page(score_image)

    # 结果完全来自重试响应：截断的半截 JSON 不参与拼接。
    assert result.jianpu_text == "1=C\n4/4\n1 2 3 4 |"
    assert any("截断" in warning for warning in result.warnings)
    assert len(captured) == 2

    first_prompt = captured[0]["messages"][1]["content"][0]["text"]
    second_prompt = captured[1]["messages"][1]["content"][0]["text"]
    # 完整 schema 含 confidence/warnings 字段；紧凑 schema 只保留核心字段。
    assert '"confidence"' in first_prompt
    assert '"confidence"' not in second_prompt
    assert '"warnings"' not in second_prompt
    # 两次请求都保持 json_object 模式（全新完整 JSON 请求，不做拼接续写）。
    assert captured[0]["response_format"] == {"type": "json_object"}
    assert captured[1]["response_format"] == {"type": "json_object"}


def test_vision_raises_clear_error_when_compact_retry_truncated(
    monkeypatch, real_prompt_config, score_image: Path
) -> None:
    captured = _install_post(
        monkeypatch,
        [
            FakePostResponse('{"jianpu_text": "1=C\\n4/4\\n1 2 |', "length"),
            FakePostResponse('{"jianpu_text": "1=C\\n4/4\\n1 2 |', "length"),
        ],
    )

    provider = OpenAICompatibleVisionProvider(api_key="test-key")

    with pytest.raises(AITranscriptionError, match="max_tokens"):
        provider.transcribe_page(score_image)

    assert len(captured) == 2


def test_vision_skips_retry_when_not_truncated(
    monkeypatch, real_prompt_config, score_image: Path
) -> None:
    captured = _install_post(
        monkeypatch,
        [
            FakePostResponse(
                '{"jianpu_text":"1=C\\n4/4\\n1 2 3 4 |","title":null,"key":"C","meter":"4/4"}',
                "stop",
            )
        ],
    )

    provider = OpenAICompatibleVisionProvider(api_key="test-key")
    result = provider.transcribe_page(score_image)

    assert result.jianpu_text == "1=C\n4/4\n1 2 3 4 |"
    assert not any("截断" in warning for warning in result.warnings)
    assert len(captured) == 1


def test_vision_treats_missing_finish_reason_as_complete(
    monkeypatch, real_prompt_config, score_image: Path
) -> None:
    captured = _install_post(
        monkeypatch,
        [
            FakePostResponse(
                '{"jianpu_text":"1=C\\n4/4\\n1 2 3 4 |"}',
                None,
            )
        ],
    )

    provider = OpenAICompatibleVisionProvider(api_key="test-key")
    result = provider.transcribe_page(score_image)

    assert result.jianpu_text == "1=C\n4/4\n1 2 3 4 |"
    assert len(captured) == 1
