from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from ...exec.tasks.actions import TaskActions
from ...models.tasks.entities import TaskStatus

ProgressCallback = Callable[[str, int, str], None]
SyncTask = Callable[[ProgressCallback], Any]


async def run_sync_task(task_id: str, tasks: TaskActions, action: SyncTask) -> None:
    loop = asyncio.get_running_loop()
    await tasks.start(task_id)

    def progress(stage: str, percent: int, message: str) -> None:
        future = asyncio.run_coroutine_threadsafe(
            tasks.update(
                task_id,
                status=TaskStatus.RUNNING,
                stage=stage,
                percent=max(0, min(99, int(percent))),
                message=message,
            ),
            loop,
        )
        try:
            future.result(timeout=5)
        except Exception:
            return

    try:
        result = await asyncio.to_thread(action, progress)
    except Exception as exc:
        await tasks.fail(task_id, _error_message(exc))
        return

    await tasks.complete(task_id, _result_to_dict(result))


def _result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(exclude_none=True)
    if hasattr(result, "dict"):
        return result.dict(exclude_none=True)
    if isinstance(result, dict):
        return result
    return {"value": result}


def _error_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, str):
        return detail
    if detail is not None:
        return str(detail)
    return str(exc)
