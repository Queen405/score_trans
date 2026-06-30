from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ...models.history.entities import (
    HistoryBatch,
    HistoryBatchSummary,
    HistoryPage,
    HistoryRenderPageOcrText,
)
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "history.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "history.db"


class HistoryDao:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if db_path is None:
            migrate_legacy_sqlite(self.db_path, LEGACY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
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
                    jianpu_text TEXT NOT NULL DEFAULT '',
                    render_page_file_ids TEXT NOT NULL DEFAULT '[]',
                    render_page_ocr_texts TEXT NOT NULL DEFAULT '[]',
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
                    task_id TEXT NOT NULL DEFAULT '',
                    musicxml_file_id TEXT NOT NULL DEFAULT '',
                    jianpu_text TEXT NOT NULL DEFAULT '',
                    ocr_text TEXT NOT NULL DEFAULT '',
                    svg_file_id TEXT NOT NULL DEFAULT '',
                    overlay_svg_file_id TEXT NOT NULL DEFAULT '',
                    start_measure_number INTEGER,
                    status TEXT NOT NULL DEFAULT 'completed',
                    error_message TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._ensure_indexes(conn)
            conn.commit()

    def list_batch_summaries(self) -> list[HistoryBatchSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    b.id,
                    b.created_at,
                    b.page_count,
                    b.status,
                    COALESCE(
                        (
                            SELECT p.input_file_name
                            FROM history_page p
                            WHERE p.batch_id = b.id
                            ORDER BY p.id ASC
                            LIMIT 1
                        ),
                        ''
                    ) AS first_file_name,
                    COALESCE(
                        (
                            SELECT MAX(p.completed_at)
                            FROM history_page p
                            WHERE p.batch_id = b.id AND p.completed_at != ''
                        ),
                        ''
                    ) AS last_completed_at
                FROM history_batch b
                ORDER BY b.id DESC
                """
            ).fetchall()
            return [
                HistoryBatchSummary(
                    id=row["id"],
                    created_at=row["created_at"],
                    page_count=row["page_count"],
                    status=row["status"],
                    first_file_name=row["first_file_name"],
                    last_completed_at=row["last_completed_at"],
                )
                for row in rows
            ]

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

    def get_page(self, page_id: int) -> HistoryPage | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM history_page WHERE id = ?", (page_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_page(row)

    def create_batch(
        self,
        pages: list[HistoryPage],
        render_page_file_ids: list[str] | None = None,
        jianpu_text: str = "",
        render_page_ocr_texts: list[HistoryRenderPageOcrText] | None = None,
    ) -> HistoryBatch:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO history_batch
                    (page_count, jianpu_text, render_page_file_ids, render_page_ocr_texts)
                VALUES (?, ?, ?, ?)
                """,
                (
                    len(pages),
                    jianpu_text,
                    _dump_render_page_file_ids(render_page_file_ids or []),
                    _dump_render_page_ocr_texts(render_page_ocr_texts or []),
                ),
            )
            batch_id = cursor.lastrowid
            for page in pages:
                conn.execute(
                    """
                    INSERT INTO history_page
                        (batch_id, input_file_name, input_file_id, task_id, musicxml_file_id,
                         jianpu_text, ocr_text, svg_file_id, overlay_svg_file_id,
                         start_measure_number, status, error_message, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        batch_id,
                        page.input_file_name,
                        page.input_file_id,
                        page.task_id,
                        page.musicxml_file_id,
                        page.jianpu_text,
                        page.ocr_text,
                        page.svg_file_id,
                        page.overlay_svg_file_id,
                        page.start_measure_number,
                        page.status,
                        page.error_message,
                        page.completed_at,
                    ),
                )
            batch_status = _batch_status([p.status for p in pages])
            conn.execute(
                "UPDATE history_batch SET status = ? WHERE id = ?",
                (batch_status, batch_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            return self._row_to_batch(conn, row)

    def update_batch_render_pages(
        self, batch_id: int, render_page_file_ids: list[str]
    ) -> HistoryBatch | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not exists:
                return None
            conn.execute(
                "UPDATE history_batch SET render_page_file_ids = ? WHERE id = ?",
                (_dump_render_page_file_ids(render_page_file_ids), batch_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            return self._row_to_batch(conn, row)

    def update_batch_jianpu_text(
        self, batch_id: int, jianpu_text: str
    ) -> HistoryBatch | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not exists:
                return None
            conn.execute(
                "UPDATE history_batch SET jianpu_text = ? WHERE id = ?",
                (jianpu_text, batch_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            return self._row_to_batch(conn, row)

    def update_batch_render_page_ocr_texts(
        self,
        batch_id: int,
        render_page_ocr_texts: list[HistoryRenderPageOcrText],
    ) -> HistoryBatch | None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not exists:
                return None
            conn.execute(
                "UPDATE history_batch SET render_page_ocr_texts = ? WHERE id = ?",
                (_dump_render_page_ocr_texts(render_page_ocr_texts), batch_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            return self._row_to_batch(conn, row)

    def update_page(
        self,
        page_id: int,
        *,
        task_id: str | None = None,
        jianpu_text: str | None = None,
        ocr_text: str | None = None,
        svg_file_id: str | None = None,
        overlay_svg_file_id: str | None = None,
        musicxml_file_id: str | None = None,
        start_measure_number: int | None = None,
        status: str | None = None,
        error_message: str | None = None,
    ) -> HistoryPage | None:
        updates: list[str] = []
        values: list[str | int] = []
        for field, value in (
            ("task_id", task_id),
            ("jianpu_text", jianpu_text),
            ("ocr_text", ocr_text),
            ("svg_file_id", svg_file_id),
            ("overlay_svg_file_id", overlay_svg_file_id),
            ("musicxml_file_id", musicxml_file_id),
            ("start_measure_number", start_measure_number),
            ("status", status),
            ("error_message", error_message),
        ):
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT id, batch_id, completed_at FROM history_page WHERE id = ?",
                (page_id,),
            ).fetchone()
            if not exists:
                return None
            if status in ("completed", "failed") and not exists["completed_at"]:
                updates.append("completed_at = datetime('now', 'localtime')")
            if updates:
                values.append(page_id)
                conn.execute(
                    f"UPDATE history_page SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
                self._refresh_batch_status(conn, exists["batch_id"])
                conn.commit()
            row = conn.execute(
                "SELECT * FROM history_page WHERE id = ?", (page_id,)
            ).fetchone()
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
        status = _batch_status([row["status"] for row in rows])
        conn.execute(
            "UPDATE history_batch SET status = ?, page_count = ? WHERE id = ?",
            (status, len(rows), batch_id),
        )

    @staticmethod
    def _migrate_db(conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(history_page)").fetchall()
        }
        if "ocr_text" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN ocr_text TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        if "task_id" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN task_id TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        if "start_measure_number" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN start_measure_number INTEGER"
            )
            conn.commit()
        if "completed_at" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        if "overlay_svg_file_id" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN overlay_svg_file_id TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        batch_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(history_batch)").fetchall()
        }
        if "render_page_file_ids" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN render_page_file_ids TEXT NOT NULL DEFAULT '[]'"
            )
            conn.commit()
        if "jianpu_text" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN jianpu_text TEXT NOT NULL DEFAULT ''"
            )
            conn.commit()
        if "render_page_ocr_texts" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN render_page_ocr_texts TEXT NOT NULL DEFAULT '[]'"
            )
            conn.commit()
        HistoryDao._ensure_indexes(conn)

    @staticmethod
    def _ensure_indexes(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_page_batch_id_id
            ON history_page(batch_id, id)
            """
        )

    def _row_to_batch(self, conn: sqlite3.Connection, row: sqlite3.Row) -> HistoryBatch:
        batch = HistoryBatch(
            id=row["id"],
            created_at=row["created_at"],
            page_count=row["page_count"],
            status=row["status"],
            jianpu_text=row["jianpu_text"] if "jianpu_text" in row.keys() else "",
            render_page_file_ids=_load_render_page_file_ids(
                row["render_page_file_ids"]
                if "render_page_file_ids" in row.keys()
                else "[]"
            ),
            render_page_ocr_texts=_load_render_page_ocr_texts(
                row["render_page_ocr_texts"]
                if "render_page_ocr_texts" in row.keys()
                else "[]"
            ),
        )
        page_rows = conn.execute(
            "SELECT * FROM history_page WHERE batch_id = ? ORDER BY id ASC",
            (batch.id,),
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
            task_id=row["task_id"] if "task_id" in row.keys() else "",
            musicxml_file_id=row["musicxml_file_id"],
            jianpu_text=row["jianpu_text"],
            ocr_text=row["ocr_text"] if "ocr_text" in row.keys() else "",
            svg_file_id=row["svg_file_id"],
            overlay_svg_file_id=row["overlay_svg_file_id"]
            if "overlay_svg_file_id" in row.keys()
            else "",
            start_measure_number=row["start_measure_number"]
            if "start_measure_number" in row.keys()
            else None,
            status=row["status"],
            error_message=row["error_message"],
            completed_at=row["completed_at"] if "completed_at" in row.keys() else "",
        )


def _batch_status(statuses: list[str]) -> str:
    active_statuses = {"pending", "processing", "waiting"}
    known_statuses = {"completed", "failed", "unrecognized", *active_statuses}
    if any(status == "failed" or status not in known_statuses for status in statuses):
        return "failed"
    if any(status == "waiting" for status in statuses):
        return "waiting"
    if any(status in active_statuses for status in statuses):
        return "processing"
    return "completed"


def _dump_render_page_file_ids(file_ids: list[str]) -> str:
    return json.dumps([file_id for file_id in file_ids if file_id], ensure_ascii=False)


def _load_render_page_file_ids(payload: str) -> list[str]:
    try:
        raw = json.loads(payload or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item)]


def _dump_render_page_ocr_texts(items: list[HistoryRenderPageOcrText]) -> str:
    return json.dumps(
        [
            {"page_index": int(item.page_index), "ocr_text": item.ocr_text}
            for item in items
            if item.page_index >= 0
        ],
        ensure_ascii=False,
    )


def _load_render_page_ocr_texts(payload: str) -> list[HistoryRenderPageOcrText]:
    try:
        raw = json.loads(payload or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    items: list[HistoryRenderPageOcrText] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            page_index = int(entry.get("page_index", -1))
        except (TypeError, ValueError):
            continue
        if page_index < 0:
            continue
        items.append(
            HistoryRenderPageOcrText(
                page_index=page_index,
                ocr_text=str(entry.get("ocr_text") or ""),
            )
        )
    return items
