from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .env_file import PROJECT_ROOT

DEFAULT_DB_PATH = PROJECT_ROOT / "work" / "history.db"


@dataclass(slots=True)
class HistoryEntry:
    id: int = 0
    created_at: str = ""
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    svg_file_id: str = ""
    status: str = "completed"
    error_message: str = ""


class HistoryService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        expected_cols = {
            "id", "created_at", "input_file_name", "input_file_id",
            "musicxml_file_id", "jianpu_text", "svg_file_id",
            "status", "error_message",
        }
        with self._connect() as conn:
            # Check if the table exists and has the expected schema
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
            ).fetchall()
            if rows:
                existing = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(history)").fetchall()
                }
                if not expected_cols.issubset(existing):
                    conn.execute("DROP TABLE history")
                    conn.commit()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    input_file_name TEXT NOT NULL DEFAULT '',
                    input_file_id TEXT NOT NULL DEFAULT '',
                    musicxml_file_id TEXT NOT NULL DEFAULT '',
                    jianpu_text TEXT NOT NULL DEFAULT '',
                    svg_file_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    error_message TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def list_entries(self) -> list[HistoryEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM history ORDER BY id DESC").fetchall()
        return [self._row_to_entry(row) for row in rows]

    def get_entry(self, entry_id: int) -> HistoryEntry | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM history WHERE id = ?", (entry_id,)).fetchone()
        return self._row_to_entry(row) if row else None

    def create_entry(self, entry: HistoryEntry) -> HistoryEntry:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO history
                    (input_file_name, input_file_id, musicxml_file_id,
                     jianpu_text, svg_file_id, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.input_file_name,
                    entry.input_file_id,
                    entry.musicxml_file_id,
                    entry.jianpu_text,
                    entry.svg_file_id,
                    entry.status,
                    entry.error_message,
                ),
            )
            entry.id = cursor.lastrowid
            conn.commit()
            row = conn.execute("SELECT created_at FROM history WHERE id = ?", (entry.id,)).fetchone()
            if row:
                entry.created_at = row["created_at"]
        return entry

    def delete_entry(self, entry_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_all(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history")
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            created_at=row["created_at"],
            input_file_name=row["input_file_name"],
            input_file_id=row["input_file_id"],
            musicxml_file_id=row["musicxml_file_id"],
            jianpu_text=row["jianpu_text"],
            svg_file_id=row["svg_file_id"],
            status=row["status"],
            error_message=row["error_message"],
        )
