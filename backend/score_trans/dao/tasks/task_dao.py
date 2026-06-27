from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ...models.tasks.entities import TaskProgress, TaskStatus
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "tasks.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "tasks.db"


class TaskDao:
    """SQLite persistence for background task state."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if db_path is None:
            migrate_legacy_sqlite(self.db_path, LEGACY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_state (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'pending',
                    stage TEXT NOT NULL DEFAULT '',
                    percent INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    result TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL
                )
                """
            )
            conn.commit()

    def save(self, progress: TaskProgress) -> None:
        result_json = (
            json.dumps(progress.result, ensure_ascii=False)
            if progress.result is not None
            else None
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_state (task_id, status, stage, percent, message, result, error,
                                        created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status=excluded.status, stage=excluded.stage, percent=excluded.percent,
                    message=excluded.message, result=excluded.result, error=excluded.error,
                    updated_at=excluded.updated_at, expires_at=excluded.expires_at
                """,
                (
                    progress.task_id,
                    progress.status.value,
                    progress.stage,
                    progress.percent,
                    progress.message,
                    result_json,
                    progress.error,
                    progress.created_at,
                    progress.updated_at,
                    progress.expires_at,
                ),
            )
            conn.commit()

    def load(self, task_id: str) -> TaskProgress | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_state WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_progress(row)

    def load_active(self, now: float | None = None) -> list[TaskProgress]:
        """Load non-expired tasks for recovery on startup."""
        now = time.time() if now is None else now
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM task_state WHERE expires_at IS NULL OR expires_at > ?",
                (now,),
            ).fetchall()
            return [self._row_to_progress(r) for r in rows]

    def delete(self, task_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM task_state WHERE task_id = ?", (task_id,))
            conn.commit()

    def delete_expired(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM task_state WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_progress(row: sqlite3.Row) -> TaskProgress:
        result_raw = row["result"]
        result: dict[str, Any] | None = json.loads(result_raw) if result_raw else None
        return TaskProgress(
            task_id=row["task_id"],
            status=TaskStatus(row["status"]),
            stage=row["stage"],
            percent=row["percent"],
            message=row["message"],
            result=result,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )
