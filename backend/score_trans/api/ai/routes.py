from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..dependencies import get_ai_actions, get_task_actions
from ..tasks.background import run_sync_task, schedule_background_task
from ...exec.ai.actions import AiActions
from ...exec.tasks.actions import TaskActions
from ...models.ai.entities import AiChatMessage, AiChatSession
from ...models.ai.schemas import (
    AiChatMessageResponse,
    AiChatRequest,
    AiChatResponse,
    AiChatSessionCreateRequest,
    AiChatSessionResponse,
    AiTranscribeRequest,
)
from ...models.tasks.entities import ProgressCallback
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transcribe", response_model=TaskSubmitResponse)
async def transcribe_score(
    request: Request,
    req: AiTranscribeRequest,
    actions: AiActions = Depends(get_ai_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    task_id = tasks.create_task()

    def action(progress: ProgressCallback):
        return actions.transcribe_score(req, progress_callback=progress)

    schedule_background_task(request.app, task_id, run_sync_task(task_id, tasks, action))
    return TaskSubmitResponse(task_id=task_id)


@router.get("/chat/sessions", response_model=list[AiChatSessionResponse])
async def list_chat_sessions(actions: AiActions = Depends(get_ai_actions)):
    return [_session_response(session) for session in actions.list_chat_sessions()]


@router.post("/chat/sessions", response_model=AiChatSessionResponse)
async def create_chat_session(
    req: AiChatSessionCreateRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    return _session_response(actions.create_chat_session(req.title))


@router.get("/chat/sessions/{session_id}/messages", response_model=list[AiChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    actions: AiActions = Depends(get_ai_actions),
):
    return [_message_response(message) for message in actions.get_chat_messages(session_id)]


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    actions: AiActions = Depends(get_ai_actions),
):
    return actions.delete_chat_session(session_id)


@router.post("/chat", response_model=AiChatResponse)
async def send_chat_message(
    req: AiChatRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    session_id, assistant_message, messages = await asyncio.to_thread(
        actions.send_chat_message,
        req.message,
        session_id=req.session_id,
        jianpu_text=req.jianpu_text,
    )
    return AiChatResponse(
        session_id=session_id,
        message=_message_response(assistant_message),
        messages=[_message_response(message) for message in messages],
    )


@router.post("/chat/stream")
async def stream_chat_message(
    req: AiChatRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    def events() -> Iterator[str]:
        final_message: AiChatMessage | None = None
        try:
            for event, payload in actions.stream_chat_message(
                req.message,
                session_id=req.session_id,
                jianpu_text=req.jianpu_text,
            ):
                if event == "session":
                    yield _sse("session", {"session_id": payload})
                elif event == "delta":
                    yield _sse("delta", {"content": payload})
                elif event == "message" and isinstance(payload, AiChatMessage):
                    final_message = payload
                elif event == "messages" and isinstance(payload, list):
                    yield _sse(
                        "done",
                        {
                            "session_id": final_message.session_id if final_message else "",
                            "message": _message_response(final_message).model_dump()
                            if final_message
                            else None,
                            "messages": [
                                _message_response(message).model_dump()
                                for message in payload
                            ],
                        },
                    )
        except Exception as exc:
            yield _sse("error", {"error": str(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


def _session_response(session: AiChatSession) -> AiChatSessionResponse:
    return AiChatSessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_response(message: AiChatMessage) -> AiChatMessageResponse:
    return AiChatMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
