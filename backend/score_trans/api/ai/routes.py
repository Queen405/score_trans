from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..dependencies import get_ai_actions, get_task_actions
from ...exec.ai.actions import AiActions
from ...exec.tasks.actions import TaskActions
from ...models.ai.schemas import (
    AiChatMessageResponse,
    AiChatRequest,
    AiChatResponse,
    AiChatSessionCreateRequest,
    AiChatSessionResponse,
    AiTranscribeRequest,
)
from ...models.tasks.schemas import TaskSubmitResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/transcribe", response_model=TaskSubmitResponse)
async def transcribe_score(
    request: Request,
    req: AiTranscribeRequest,
    actions: AiActions = Depends(get_ai_actions),
    tasks: TaskActions = Depends(get_task_actions),
):
    return actions.submit_transcribe_task(request.app, req, tasks)


@router.get("/chat/sessions", response_model=list[AiChatSessionResponse])
async def list_chat_sessions(actions: AiActions = Depends(get_ai_actions)):
    return actions.list_chat_session_responses()


@router.post("/chat/sessions", response_model=AiChatSessionResponse)
async def create_chat_session(
    req: AiChatSessionCreateRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    return actions.create_chat_session_response(req.title)


@router.get("/chat/sessions/{session_id}/messages", response_model=list[AiChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    actions: AiActions = Depends(get_ai_actions),
):
    return actions.get_chat_message_responses(session_id)


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
    return await actions.send_chat_message_response_async(req)


@router.post("/chat/stream")
async def stream_chat_message(
    req: AiChatRequest,
    actions: AiActions = Depends(get_ai_actions),
):
    return StreamingResponse(
        actions.stream_chat_events(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
