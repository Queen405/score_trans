from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import cast

from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ...models.common.sentinels import UNSET, UnsetType
from ...models.history.entities import (
    HistoryBatch,
    HistoryBatchSummary,
    HistoryPage,
    HistoryRenderPageOcrText,
)
from ...models.provenance.schemas import SourceTextAttachment, TextAnchor
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "history.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "history.db"
_SCHEMA_VERSION = 1

_PAGE_FILE_ID_COLUMNS = (
    "input_file_id",
    "musicxml_file_id",
    "svg_file_id",
    "overlay_svg_file_id",
    "overlay_file_id",
    "source_map_file_id",
)


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
            conn.execute("BEGIN IMMEDIATE")
            try:
                if self._table_exists(conn, "history_batch"):
                    self._migrate_db(conn)
                else:
                    self._create_tables(conn)
                    if self._table_exists(conn, "history"):
                        self._migrate_legacy_history_rows(conn)
                    self._ensure_indexes(conn)
                    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
                (table_name,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _create_tables(conn: sqlite3.Connection) -> None:
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
                text_attachments TEXT NOT NULL DEFAULT '[]',
                svg_file_id TEXT NOT NULL DEFAULT '',
                overlay_svg_file_id TEXT NOT NULL DEFAULT '',
                overlay_file_id TEXT NOT NULL DEFAULT '',
                source_map_file_id TEXT NOT NULL DEFAULT '',
                text_hash TEXT NOT NULL DEFAULT '',
                text_anchors TEXT NOT NULL DEFAULT '[]',
                start_measure_number INTEGER,
                status TEXT NOT NULL DEFAULT 'completed',
                error_message TEXT NOT NULL DEFAULT '',
                completed_at TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0
            )
            """
        )

    @staticmethod
    def _migrate_legacy_history_rows(conn: sqlite3.Connection) -> None:
        expected_columns = {
            "id",
            "created_at",
            "input_file_name",
            "input_file_id",
            "musicxml_file_id",
            "jianpu_text",
            "svg_file_id",
            "status",
            "error_message",
        }
        actual_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(history)")
        }
        missing = expected_columns - actual_columns
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise RuntimeError(
                f"旧 history 表结构无法安全迁移，缺少字段：{missing_text}"
            )
        if HistoryDao._table_exists(conn, "history_legacy_backup"):
            raise RuntimeError(
                "检测到 history 和 history_legacy_backup 同时存在，"
                "为避免覆盖备份，已停止自动迁移"
            )

        rows = conn.execute("SELECT * FROM history ORDER BY id").fetchall()
        for row in rows:
            batch_id = int(row["id"])
            created_at = str(row["created_at"] or "")
            jianpu_text = str(row["jianpu_text"] or "")
            status = str(row["status"] or "completed")
            error_message = str(row["error_message"] or "")
            completed_at = created_at if status in {"completed", "failed"} else ""
            conn.execute(
                """
                INSERT INTO history_batch (
                    id, created_at, page_count, jianpu_text,
                    render_page_file_ids, render_page_ocr_texts, status
                )
                VALUES (?, ?, 1, ?, '[]', '[]', ?)
                """,
                (batch_id, created_at, jianpu_text, status),
            )
            conn.execute(
                """
                INSERT INTO history_page (
                    id, batch_id, input_file_name, input_file_id, musicxml_file_id,
                    jianpu_text, svg_file_id, status, error_message, completed_at, position
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    batch_id,
                    batch_id,
                    str(row["input_file_name"] or ""),
                    str(row["input_file_id"] or ""),
                    str(row["musicxml_file_id"] or ""),
                    jianpu_text,
                    str(row["svg_file_id"] or ""),
                    status,
                    error_message,
                    completed_at,
                ),
            )
        conn.execute("ALTER TABLE history RENAME TO history_legacy_backup")

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
                            ORDER BY p.position ASC, p.id ASC
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
            batch_rows = conn.execute(
                "SELECT * FROM history_batch ORDER BY id DESC"
            ).fetchall()
            page_rows = conn.execute(
                """
                SELECT *
                FROM history_page
                ORDER BY batch_id DESC, position ASC, id ASC
                """
            ).fetchall()

        pages_by_batch: dict[int, list[sqlite3.Row]] = {}
        for page_row in page_rows:
            pages_by_batch.setdefault(int(page_row["batch_id"]), []).append(page_row)
        return [
            self._row_to_batch_rows(
                batch_row,
                pages_by_batch.get(int(batch_row["id"]), []),
            )
            for batch_row in batch_rows
        ]

    def referenced_file_ids(self) -> set[str]:
        """Return every upload file ID retained by history records."""
        referenced: set[str] = set()
        with self._connect() as conn:
            page_rows = conn.execute(
                f"SELECT {', '.join(_PAGE_FILE_ID_COLUMNS)} FROM history_page"
            ).fetchall()
            batch_rows = conn.execute(
                "SELECT render_page_file_ids FROM history_batch"
            ).fetchall()

        for row in page_rows:
            referenced.update(
                str(row[column]) for column in _PAGE_FILE_ID_COLUMNS if row[column]
            )
        for row in batch_rows:
            referenced.update(_load_render_page_file_ids(row["render_page_file_ids"]))
        return referenced

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
            for index, page in enumerate(pages):
                conn.execute(
                    """
                    INSERT INTO history_page
                        (batch_id, input_file_name, input_file_id, task_id, musicxml_file_id,
                         jianpu_text, ocr_text, svg_file_id, overlay_svg_file_id,
                         text_attachments, overlay_file_id, source_map_file_id, text_hash,
                         text_anchors, start_measure_number, status, error_message,
                         completed_at, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        _dump_text_attachments(page.text_attachments),
                        page.overlay_file_id,
                        page.source_map_file_id,
                        page.text_hash,
                        _dump_text_anchors(page.text_anchors),
                        page.start_measure_number,
                        page.status,
                        page.error_message,
                        page.completed_at,
                        index,
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
        text_attachments: list[SourceTextAttachment] | None = None,
        svg_file_id: str | None = None,
        overlay_svg_file_id: str | None = None,
        overlay_file_id: str | None = None,
        source_map_file_id: str | None = None,
        text_hash: str | None = None,
        text_anchors: list[TextAnchor] | None = None,
        musicxml_file_id: str | None = None,
        start_measure_number: int | None | UnsetType = UNSET,
        status: str | None = None,
        error_message: str | None = None,
    ) -> HistoryPage | None:
        updates: list[str] = []
        values: list[str | int | None] = []
        for field, value in (
            ("task_id", task_id),
            ("jianpu_text", jianpu_text),
            ("ocr_text", ocr_text),
            (
                "text_attachments",
                _dump_text_attachments(text_attachments)
                if text_attachments is not None
                else None,
            ),
            ("svg_file_id", svg_file_id),
            ("overlay_svg_file_id", overlay_svg_file_id),
            ("overlay_file_id", overlay_file_id),
            ("source_map_file_id", source_map_file_id),
            ("text_hash", text_hash),
            (
                "text_anchors",
                _dump_text_anchors(text_anchors) if text_anchors is not None else None,
            ),
            ("musicxml_file_id", musicxml_file_id),
            ("status", status),
            ("error_message", error_message),
        ):
            if value is not None:
                updates.append(f"{field} = ?")
                values.append(value)
        if start_measure_number is not UNSET:
            updates.append("start_measure_number = ?")
            values.append(cast(int | None, start_measure_number))

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

    def reorder_pages(
        self,
        batch_id: int,
        jianpu_text: str,
        page_orders: list[tuple[int, str, int | None]],
    ) -> HistoryBatch | None:
        with self._connect() as conn:
            batch_row = conn.execute(
                "SELECT id FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            if not batch_row:
                return None

            existing_pages = conn.execute(
                "SELECT id, status FROM history_page WHERE batch_id = ?",
                (batch_id,),
            ).fetchall()
            existing_ids = {row["id"] for row in existing_pages}
            requested_ids = [item[0] for item in page_orders]

            if len(requested_ids) != len(set(requested_ids)):
                raise ValueError("Duplicate page IDs in reorder request")
            if set(requested_ids) != existing_ids:
                raise ValueError("Page IDs do not match batch pages")

            active_statuses = {"pending", "processing", "waiting"}
            active_pages = [
                row["id"] for row in existing_pages if row["status"] in active_statuses
            ]
            if active_pages:
                raise ValueError(
                    f"Cannot reorder while pages have active tasks: {active_pages}"
                )

            marker_count = len(re.findall(r"//\s*@page\s+\d+", jianpu_text))
            if marker_count > 0 and marker_count != len(page_orders):
                raise ValueError(
                    f"Batch jianpu_text has {marker_count} page markers "
                    f"but {len(page_orders)} pages were provided"
                )

            for position, (
                page_id,
                page_jianpu_text,
                start_measure_number,
            ) in enumerate(page_orders):
                conn.execute(
                    """
                    UPDATE history_page
                    SET position = ?, jianpu_text = ?, start_measure_number = ?
                    WHERE id = ? AND batch_id = ?
                    """,
                    (
                        position,
                        page_jianpu_text,
                        start_measure_number,
                        page_id,
                        batch_id,
                    ),
                )

            conn.execute(
                """
                UPDATE history_batch
                SET jianpu_text = ?,
                    render_page_file_ids = '[]',
                    render_page_ocr_texts = '[]'
                WHERE id = ?
                """,
                (jianpu_text, batch_id),
            )
            conn.commit()

            row = conn.execute(
                "SELECT * FROM history_batch WHERE id = ?", (batch_id,)
            ).fetchone()
            return self._row_to_batch(conn, row)

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
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version > _SCHEMA_VERSION:
            raise RuntimeError(
                "History database schema is newer than this application "
                f"(database={version}, supported={_SCHEMA_VERSION})"
            )
        if version == _SCHEMA_VERSION:
            HistoryDao._ensure_indexes(conn)
            return

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(history_page)").fetchall()
        }
        if "ocr_text" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN ocr_text TEXT NOT NULL DEFAULT ''"
            )
        if "task_id" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN task_id TEXT NOT NULL DEFAULT ''"
            )
        if "start_measure_number" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN start_measure_number INTEGER"
            )
        if "completed_at" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN completed_at TEXT NOT NULL DEFAULT ''"
            )
        if "position" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
            )
            conn.execute(
                """
                UPDATE history_page
                SET position = (
                    SELECT COUNT(*)
                    FROM history_page AS p2
                    WHERE p2.batch_id = history_page.batch_id
                      AND p2.id < history_page.id
                )
                """
            )
        if "overlay_svg_file_id" not in columns:
            conn.execute(
                "ALTER TABLE history_page ADD COLUMN overlay_svg_file_id TEXT NOT NULL DEFAULT ''"
            )
        for column, definition in (
            ("overlay_file_id", "TEXT NOT NULL DEFAULT ''"),
            ("source_map_file_id", "TEXT NOT NULL DEFAULT ''"),
            ("text_hash", "TEXT NOT NULL DEFAULT ''"),
            ("text_anchors", "TEXT NOT NULL DEFAULT '[]'"),
            ("text_attachments", "TEXT NOT NULL DEFAULT '[]'"),
        ):
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE history_page ADD COLUMN {column} {definition}"
                )
        batch_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(history_batch)").fetchall()
        }
        if "render_page_file_ids" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN render_page_file_ids TEXT NOT NULL DEFAULT '[]'"
            )
        if "jianpu_text" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN jianpu_text TEXT NOT NULL DEFAULT ''"
            )
        if "render_page_ocr_texts" not in batch_columns:
            conn.execute(
                "ALTER TABLE history_batch ADD COLUMN render_page_ocr_texts TEXT NOT NULL DEFAULT '[]'"
            )
        HistoryDao._ensure_indexes(conn)
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    @staticmethod
    def _ensure_indexes(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_page_batch_id_id
            ON history_page(batch_id, id)
            """
        )

    def _row_to_batch(self, conn: sqlite3.Connection, row: sqlite3.Row) -> HistoryBatch:
        page_rows = conn.execute(
            "SELECT * FROM history_page WHERE batch_id = ? ORDER BY position ASC, id ASC",
            (row["id"],),
        ).fetchall()
        return self._row_to_batch_rows(row, page_rows)

    def _row_to_batch_rows(
        self,
        row: sqlite3.Row,
        page_rows: list[sqlite3.Row],
    ) -> HistoryBatch:
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
            text_attachments=_load_text_attachments(
                row["text_attachments"] if "text_attachments" in row.keys() else "[]"
            ),
            svg_file_id=row["svg_file_id"],
            overlay_svg_file_id=row["overlay_svg_file_id"]
            if "overlay_svg_file_id" in row.keys()
            else "",
            overlay_file_id=(
                row["overlay_file_id"] if "overlay_file_id" in row.keys() else ""
            ),
            source_map_file_id=(
                row["source_map_file_id"] if "source_map_file_id" in row.keys() else ""
            ),
            text_hash=row["text_hash"] if "text_hash" in row.keys() else "",
            text_anchors=_load_text_anchors(
                row["text_anchors"] if "text_anchors" in row.keys() else "[]"
            ),
            start_measure_number=row["start_measure_number"]
            if "start_measure_number" in row.keys()
            else None,
            status=row["status"],
            error_message=row["error_message"],
            completed_at=row["completed_at"] if "completed_at" in row.keys() else "",
            position=row["position"] if "position" in row.keys() else 0,
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


def _dump_text_anchors(items: list[TextAnchor]) -> str:
    return json.dumps(
        [item.model_dump() for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_text_anchors(payload: str) -> list[TextAnchor]:
    try:
        raw = json.loads(payload or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    anchors: list[TextAnchor] = []
    for item in raw:
        try:
            anchors.append(TextAnchor.model_validate(item))
        except ValueError:
            continue
    return anchors


def _dump_text_attachments(items: list[SourceTextAttachment]) -> str:
    return json.dumps(
        [item.model_dump() for item in items],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_text_attachments(payload: str) -> list[SourceTextAttachment]:
    try:
        raw = json.loads(payload or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    attachments: list[SourceTextAttachment] = []
    for item in raw:
        try:
            attachments.append(SourceTextAttachment.model_validate(item))
        except ValueError:
            continue
    return attachments
