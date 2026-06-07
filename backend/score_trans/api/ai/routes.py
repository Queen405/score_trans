from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

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
