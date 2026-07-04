from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

from ...config.settings import (
    AI_TEMPERATURE,
    AI_TIMEOUT,
    ASSISTANT_API_KEY,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
)
from ...dao.ai.chat_dao import AiChatDao
from ...dao.settings.settings_dao import SettingsDao
from ...models.ai.entities import AiChatMessage, AiChatSession
from ...models.common.errors import AITranscriptionError
from ..settings.api_keys import provider_api_key
from ..settings.defaults import configured_settings_dao
from ..settings.provider_profiles import resolve_provider_profile_or_default
from .core.prompts import build_jianpu_assistant_system_prompt
from .providers._http import chat_completion_chunks, chat_completions

MEMORY_ROUNDS = 20
MAX_CONTEXT_MESSAGES = MEMORY_ROUNDS * 2
MAX_JIANPU_CONTEXT_CHARS = 12000
MAX_ASSISTANT_TOKENS = 4096


class AiChatService:
    def __init__(
        self,
        dao: AiChatDao | None = None,
        settings: SettingsDao | None = None,
    ) -> None:
        self.dao = dao or AiChatDao()
        self.settings = settings or configured_settings_dao()

    def list_sessions(self) -> list[AiChatSession]:
        return self.dao.list_sessions()

    def create_session(self, title: str | None = None) -> AiChatSession:
        return self.dao.create_session(uuid.uuid4().hex, title or "新对话")

    def get_messages(self, session_id: str) -> list[AiChatMessage]:
        if not self.dao.get_session(session_id):
            raise FileNotFoundError(f"AI 会话不存在：{session_id}")
        return self.dao.list_messages(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self.dao.delete_session(session_id)

    def send_message(
        self,
        message: str,
        *,
        session_id: str | None = None,
        jianpu_text: str | None = None,
        enable_thinking: bool | None = None,
    ) -> tuple[str, AiChatMessage, list[AiChatMessage]]:
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("消息不能为空")

        session = self._ensure_session(session_id)
        assistant_text = self._call_model(
            session.id,
            current_user_message=clean_message,
            jianpu_text=jianpu_text,
            enable_thinking=enable_thinking,
        )
        _, assistant_msg = self.dao.add_exchange(
            session.id,
            user_content=clean_message,
            assistant_content=assistant_text,
            title_if_empty=_title_from_message(clean_message),
        )
        return session.id, assistant_msg, self.dao.list_messages(session.id)

    def stream_message(
        self,
        message: str,
        *,
        session_id: str | None = None,
        jianpu_text: str | None = None,
        enable_thinking: bool | None = None,
    ) -> Iterator[tuple[str, str | AiChatMessage | list[AiChatMessage]]]:
        clean_message = message.strip()
        if not clean_message:
            raise ValueError("消息不能为空")

        session = self._ensure_session(session_id)
        yield "session", session.id
        chunks: list[str] = []
        for chunk in self._stream_model(
            session.id,
            current_user_message=clean_message,
            jianpu_text=jianpu_text,
            enable_thinking=enable_thinking,
        ):
            chunks.append(chunk)
            yield "delta", chunk

        _, assistant_msg = self.dao.add_exchange(
            session.id,
            user_content=clean_message,
            assistant_content="".join(chunks),
            title_if_empty=_title_from_message(clean_message),
        )
        yield "message", assistant_msg
        yield "messages", self.dao.list_messages(session.id)

    def _ensure_session(self, session_id: str | None) -> AiChatSession:
        if session_id:
            session = self.dao.get_session(session_id)
            if session:
                return session
        return self.create_session()

    def _call_model(
        self,
        session_id: str,
        *,
        current_user_message: str,
        jianpu_text: str | None,
        enable_thinking: bool | None,
    ) -> str:
        api_key, base_url, model = self._provider_settings()
        if not api_key:
            raise AITranscriptionError(
                "工作台 AI API key 未配置，请在设置中填写 API Key。"
            )

        messages = self._build_messages(
            session_id,
            current_user_message=current_user_message,
            jianpu_text=jianpu_text,
        )

        try:
            return chat_completions(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=messages,
                temperature=AI_TEMPERATURE,
                timeout=AI_TIMEOUT,
                max_tokens=MAX_ASSISTANT_TOKENS,
                enable_thinking=enable_thinking,
            )
        except Exception as exc:
            raise AITranscriptionError(f"工作台 AI 请求失败：{exc}") from exc

    def _stream_model(
        self,
        session_id: str,
        *,
        current_user_message: str,
        jianpu_text: str | None,
        enable_thinking: bool | None,
    ) -> Iterator[str]:
        api_key, base_url, model = self._provider_settings()
        if not api_key:
            raise AITranscriptionError(
                "工作台 AI API key 未配置，请在设置中填写 API Key。"
            )

        messages = self._build_messages(
            session_id,
            current_user_message=current_user_message,
            jianpu_text=jianpu_text,
        )
        try:
            yield from chat_completion_chunks(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=messages,
                temperature=AI_TEMPERATURE,
                timeout=AI_TIMEOUT,
                max_tokens=MAX_ASSISTANT_TOKENS,
                enable_thinking=enable_thinking,
            )
        except Exception as exc:
            raise AITranscriptionError(f"工作台 AI 请求失败：{exc}") from exc

    def _build_messages(
        self,
        session_id: str,
        *,
        current_user_message: str,
        jianpu_text: str | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": build_jianpu_assistant_system_prompt()}
        ]
        history_limit = max(0, MAX_CONTEXT_MESSAGES - 1)
        for memory in self.dao.recent_messages(session_id, history_limit):
            messages.append({"role": memory.role, "content": memory.content})
        content = current_user_message
        if jianpu_text and jianpu_text.strip():
            content = _with_jianpu_context(content, jianpu_text)
        messages.append({"role": "user", "content": content})
        return messages

    def _provider_settings(self) -> tuple[str, str, str]:
        settings = self.settings.get_all()
        profile = resolve_provider_profile_or_default(
            "assistant",
            settings.get("assistant_provider"),
        )
        api_key = (
            provider_api_key(settings, "assistant", profile.id) or ASSISTANT_API_KEY
        )
        base_url = (
            settings.get("assistant_base_url") or profile.base_url or ASSISTANT_BASE_URL
        ).rstrip("/")
        model = settings.get("assistant_model") or profile.model or ASSISTANT_MODEL
        return api_key, base_url, model


def _title_from_message(message: str) -> str:
    compact = " ".join(message.split())
    if not compact:
        return "新对话"
    return compact[:18] + ("..." if len(compact) > 18 else "")


def _with_jianpu_context(message: str, jianpu_text: str) -> str:
    context = jianpu_text.strip()
    if len(context) > MAX_JIANPU_CONTEXT_CHARS:
        context = context[:MAX_JIANPU_CONTEXT_CHARS] + "\n...（简谱上下文已截断）"
    return f"【当前工作台简谱文本】\n{context}\n\n---\n【用户问题】\n{message}"
