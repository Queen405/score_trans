from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SSEProgressEvent(BaseModel):
    task_id: str
    status: str
    stage: str
    percent: int
    message: str = ""
    error: str | None = None
    result: dict[str, Any] | None = None


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: str = "pending"
