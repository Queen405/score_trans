from __future__ import annotations

import asyncio
import inspect
import json
import sqlite3

from pydantic import BaseModel
import pytest

import score_trans.api.app as app_module
from score_trans.api.app import create_app
from score_trans.dao.tasks.task_dao import TaskDao
from score_trans.exec.tasks.background import run_sync_task, schedule_background_task
from score_trans.exec.tasks.actions import TaskActions
from score_trans.models.tasks.entities import TaskProgress, TaskStatus
from score_trans.services.tasks.task_service import TaskManager


class FakeResult(BaseModel):
    value: str


def _event_data(chunk: str) -> dict:
    assert chunk.startswith("data: ")
    return json.loads(chunk.removeprefix("data: ").strip())


def test_task_manager_streams_progress_and_result() -> None:
    async def scenario() -> list[dict]:
        manager = TaskManager()
        task_id = manager.create_task()

        async def finish_task() -> None:
            await manager.update(
                task_id,
                status=TaskStatus.RUNNING,
                stage="work",
                percent=42,
                message="working",
            )
            await manager.complete(task_id, {"ok": True})

        asyncio.create_task(finish_task())
        events: list[dict] = []
        async for chunk in manager.stream(task_id):
            if chunk.startswith(":"):
                continue
            events.append(_event_data(chunk))
            if events[-1]["status"] == "completed":
                break
        return events

    events = asyncio.run(scenario())

    assert events[0]["status"] == "pending"
    assert any(event["stage"] == "work" and event["percent"] == 42 for event in events)
    assert events[-1]["status"] == "completed"
    assert events[-1]["result"] == {"ok": True}


def test_run_sync_task_updates_task_to_completed() -> None:
    async def scenario() -> dict:
        actions = TaskActions()
        task_id = actions.create_task()

        def action(progress):
            progress("work", 33, "working")
            return FakeResult(value="done")

        await run_sync_task(task_id, actions, action)
        event = actions.get_event(task_id)
        assert event is not None
        return event.model_dump()

    event = asyncio.run(scenario())

    assert event["status"] == "completed"
    assert event["percent"] == 100
    assert event["result"] == {"value": "done"}


def test_task_manager_cleans_expired_terminal_tasks() -> None:
    clock = {"now": 100.0}
    manager = TaskManager(terminal_ttl_seconds=10, time_func=lambda: clock["now"])
    task_id = manager.create_task()

    asyncio.run(manager.complete(task_id, {"ok": True}))
    assert manager.get_progress(task_id) is not None

    clock["now"] = 111.0

    assert manager.cleanup_expired() == 1
    assert manager.get_progress(task_id) is None


def test_task_manager_marks_interrupted_tasks_failed_on_recovery(tmp_path) -> None:
    dao = TaskDao(tmp_path / "tasks.db")
    interrupted = TaskManager(dao=dao, time_func=lambda: 100.0)
    task_id = interrupted.create_task()
    asyncio.run(
        interrupted.update(
            task_id,
            status=TaskStatus.RUNNING,
            stage="omr",
            percent=99,
            message="识别中",
        )
    )

    recovered = TaskManager(
        dao=dao,
        time_func=lambda: 200.0,
        terminal_ttl_seconds=30.0,
    ).get_progress(task_id)

    assert recovered is not None
    assert recovered.status == TaskStatus.FAILED
    assert recovered.percent == 99
    assert recovered.expires_at == 230.0
    assert "重启" in (recovered.error or "")


def test_task_dao_load_active_only_returns_recoverable_statuses(tmp_path) -> None:
    dao = TaskDao(tmp_path / "tasks.db")
    for status in TaskStatus:
        dao.save(
            TaskProgress(
                task_id=status.value,
                status=status,
                expires_at=200.0,
            )
        )

    active = dao.load_active(now=100.0)

    assert {progress.status for progress in active} == {
        TaskStatus.PENDING,
        TaskStatus.RUNNING,
    }


def test_task_dao_unknown_status_becomes_failed_diagnostic(tmp_path) -> None:
    dao = TaskDao(tmp_path / "tasks.db")
    with sqlite3.connect(dao.db_path) as conn:
        conn.execute(
            """
            INSERT INTO task_state (
                task_id, status, stage, percent, message,
                created_at, updated_at
            )
            VALUES ('corrupt', 'paused-by-old-version', 'legacy', 17, 'old', 1, 2)
            """
        )

    progress = dao.load("corrupt")

    assert progress is not None
    assert progress.status == TaskStatus.FAILED
    assert "paused-by-old-version" in (progress.error or "")


def test_schedule_background_task_tracks_until_done() -> None:
    async def scenario() -> tuple[int, int]:
        app = create_app()

        async def work() -> None:
            await asyncio.sleep(0)

        task = schedule_background_task(app, "abc123", work())
        before = len(app.state.background_tasks)
        await task
        await asyncio.sleep(0)
        after = len(app.state.background_tasks)
        return before, after

    before, after = asyncio.run(scenario())

    assert before == 1
    assert after == 0


def test_app_shutdown_clears_completed_tasks_left_in_registry() -> None:
    async def scenario() -> int:
        app = create_app()
        task = asyncio.create_task(asyncio.sleep(0))
        app.state.background_tasks.add(task)
        await task

        await asyncio.wait_for(
            app_module._wait_for_background_tasks(app),
            timeout=0.1,
        )
        return len(app.state.background_tasks)

    assert asyncio.run(scenario()) == 0


def test_schedule_background_task_rejects_registration_during_shutdown() -> None:
    async def scenario() -> str:
        app = create_app()
        app.state.accepting_background_tasks = False
        coro = asyncio.sleep(0)

        with pytest.raises(RuntimeError, match="shutting down"):
            schedule_background_task(app, "too-late", coro)

        return inspect.getcoroutinestate(coro)

    assert asyncio.run(scenario()) == inspect.CORO_CLOSED


def test_global_task_events_keep_latest_update_when_subscriber_is_slow(
    tmp_path,
) -> None:
    async def scenario() -> tuple[int, int]:
        manager = TaskManager(
            dao=TaskDao(tmp_path / "tasks.db"),
            subscriber_queue_size=1,
        )
        events = manager.global_events()
        first_event = asyncio.create_task(anext(events))
        await asyncio.sleep(0)
        assert len(manager._subscribers) == 1

        await manager._broadcast(TaskProgress(task_id="task", percent=1))
        await first_event
        await manager._broadcast(TaskProgress(task_id="task", percent=2))
        await manager._broadcast(TaskProgress(task_id="task", percent=3))

        latest = _event_data(await anext(events))
        await events.aclose()
        return latest["percent"], len(manager._subscribers)

    percent, subscriber_count = asyncio.run(scenario())

    assert percent == 3
    assert subscriber_count == 0
