from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

ProgressCallback = Callable[[str, int, str], None]


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
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float | None = None


def report_progress(
    progress_callback: ProgressCallback | None, stage: str, percent: int, message: str
) -> None:
    if progress_callback is not None:
        progress_callback(stage, percent, message)
