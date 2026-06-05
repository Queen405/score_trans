from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class TaskProgress:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    stage: str = ""
    percent: int = 0
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None

