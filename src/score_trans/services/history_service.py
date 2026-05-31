from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .env_file import PROJECT_ROOT

DEFAULT_DB_PATH = PROJECT_ROOT / "work" / "history.db"


@dataclass(slots=True)
class HistoryPage:
    id: int = 0
    batch_id: int = 0
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    ocr_text: str = ""
    svg_file_id: str = ""
    status: str = "completed"
    error_message: str = ""


@dataclass(slots=True)
class HistoryBatch:
    id: int = 0
    created_at: str = ""
    page_count: int = 0
    status: str = "completed"
    pages: list[HistoryPage] = field(default_factory=list)


class HistoryService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='history_batch'"
            ).fetchall()
            if rows:
                self._migrate_db(conn)
                return
            conn.execute("DROP TABLE IF EXISTS history")
            conn.execute(
                """
                CREATE TABLE history_batch (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    page_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'completed'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE history_page (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER NOT NULL REFERENCES history_batch(id) ON DELETE CASCADE,
                    input_file_name TEXT NOT NULL DEFAULT '',
                    input_file_id TEXT NOT NULL DEFAULT '',
                    musicxml_file_id TEXT NOT NULL DEFAULT '',
                    jianpu_text TEXT NOT NULL DEFAULT '',
                    ocr_text TEXT NOT NULL DEFAULT '',
                    svg_file_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    error_message TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    def list_batches(self) -> list[HistoryBatch]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history_batch ORDER BY id DESC"
            ).fetchall()
            return [self._row_to_batch(conn, row) for row in rows]

    def get_batch(self, batch_id: int) -> HistoryBatch | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_batch(conn, row)

    def create_batch(self, pages: list[HistoryPage]) -> HistoryBatch:
        with self._connect() as conn:
            cursor = conn.execute("INSERT INTO history_batch (page_count) VALUES (?)", (len(pages),))
            batch_id = cursor.lastrowid
            for page in pages:
                conn.execute(
                    """
                    INSERT INTO history_page
                        (batch_id, input_file_name, input_file_id, musicxml_file_id,
                         jianpu_text, ocr_text, svg_file_id, status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        page.input_file_name,
                        page.input_file_id,
                        page.musicxml_file_id,
                        page.jianpu_text,
                        page.ocr_text,
                        page.svg_file_id,
                        page.status,
                        page.error_message,
                    ),
                )
            has_error = any(p.status != "completed" for p in pages)
            batch_status = "failed" if has_error else "completed"
            conn.execute(
                "UPDATE history_batch SET status = ? WHERE id = ?",
                (batch_status, batch_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM history_batch WHERE id = ?", (batch_id,)).fetchone()
            return self._row_to_batch(conn, row)

    def update_page(
        self,
        page_id: int,
        *,
        jianpu_text: str | None = None,
        ocr_text: str | None = None,
        svg_file_id: str | None = None,
        musicxml_file_id: str | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> HistoryPage | None:
        updates: list[str] = []
        values: list[str | int] = []
        for field, value in (
            ("jianpu_text", jianpu_text),
            ("ocr_text", ocr_text),
            ("svg_file_id", svg_file_id),
            ("musicxml_file_id", musicxml_file_id),
            ("status", status),
            ("error_message", error_message),
        ):
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id, batch_id FROM history_page WHERE id = ?", (page_id,)
            ).fetchone()
            if not exists:
                return None
            if updates:
                values.append(page_id)
                conn.execute(
                    f"UPDATE history_page SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
                self._refresh_batch_status(conn, exists["batch_id"])
                conn.commit()
            row = conn.execute("SELECT * FROM history_page WHERE id = ?", (page_id,)).fetchone()
            return self._row_to_page(row)

    def delete_batch(self, batch_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history_batch WHERE id = ?", (batch_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_all(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM history_batch")
            conn.commit()
            return cursor.rowcount

    def _refresh_batch_status(self, conn: sqlite3.Connection, batch_id: int) -> None:
        rows = conn.execute(
            "SELECT status FROM history_page WHERE batch_id = ?", (batch_id,)
        ).fetchall()
        status = "failed" if any(row["status"] != "completed" for row in rows) else "completed"
        conn.execute(
            "UPDATE history_batch SET status = ?, page_count = ? WHERE id = ?",
            (status, len(rows), batch_id),
        )

    @staticmethod
    def _migrate_db(conn: sqlite3.Connection) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(history_page)").fetchall()}
        if "ocr_text" not in columns:
            conn.execute("ALTER TABLE history_page ADD COLUMN ocr_text TEXT NOT NULL DEFAULT ''")
            conn.commit()

    def _row_to_batch(self, conn: sqlite3.Connection, row: sqlite3.Row) -> HistoryBatch:
        batch = HistoryBatch(
            id=row["id"],
            created_at=row["created_at"],
            page_count=row["page_count"],
            status=row["status"],
        )
        page_rows = conn.execute(
            "SELECT * FROM history_page WHERE batch_id = ? ORDER BY id", (batch.id,)
        ).fetchall()
        batch.pages = [self._row_to_page(pr) for pr in page_rows]
        return batch

    @staticmethod
    def _row_to_page(row: sqlite3.Row) -> HistoryPage:
        return HistoryPage(
            id=row["id"],
            batch_id=row["batch_id"],
            input_file_name=row["input_file_name"],
            input_file_id=row["input_file_id"],
            musicxml_file_id=row["musicxml_file_id"],
            jianpu_text=row["jianpu_text"],
            ocr_text=row["ocr_text"] if "ocr_text" in row.keys() else "",
            svg_file_id=row["svg_file_id"],
            status=row["status"],
            error_message=row["error_message"],
        )
