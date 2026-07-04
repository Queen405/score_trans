from __future__ import annotations

import sqlite3
from pathlib import Path

from ...models.ai.entities import AiChatMessage, AiChatSession
from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "ai_chat.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "ai_chat.db"


class AiChatDao:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if db_path is None:
            migrate_legacy_sqlite(self.db_path, LEGACY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_chat_session (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '新对话',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
                """
            )
            self._ensure_message_schema(conn)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_chat_message_session_id
                ON ai_chat_message(session_id, id)
                """
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_message_schema(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'ai_chat_message'
            """
        ).fetchone()
        if row is None:
            self._create_message_table(conn)
            return

        create_sql = str(row["sql"] or "").lower()
        if "'system'" in create_sql or "check" not in create_sql:
            return

        legacy_name = "ai_chat_message_legacy_role_constraint"
        collision = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (legacy_name,),
        ).fetchone()
        if collision is not None:
            raise RuntimeError(
                f"Cannot migrate ai_chat_message: {legacy_name} already exists"
            )

        conn.execute(f"ALTER TABLE ai_chat_message RENAME TO {legacy_name}")
        self._create_message_table(conn)
        conn.execute(
            f"""
            INSERT INTO ai_chat_message (id, session_id, role, content, created_at)
            SELECT id, session_id, role, content, created_at
            FROM {legacy_name}
            ORDER BY id
            """
        )
        conn.execute(f"DROP TABLE {legacy_name}")

    @staticmethod
    def _create_message_table(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE ai_chat_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES ai_chat_session(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )

    def list_sessions(self) -> list[AiChatSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ai_chat_session ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def create_session(self, session_id: str, title: str = "新对话") -> AiChatSession:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO ai_chat_session (id, title) VALUES (?, ?)",
                (session_id, title.strip() or "新对话"),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM ai_chat_session WHERE id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row)

    def get_session(self, session_id: str) -> AiChatSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ai_chat_session WHERE id = ?", (session_id,)
            ).fetchone()
        return self._row_to_session(row) if row else None

    def update_session_title(self, session_id: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ai_chat_session
                SET title = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
                """,
                (title.strip() or "新对话", session_id),
            )
            conn.commit()

    def delete_session(self, session_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM ai_chat_session WHERE id = ?", (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_message(self, session_id: str, role: str, content: str) -> AiChatMessage:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_chat_message (session_id, role, content)
                VALUES (?, ?, ?)
                """,
                (session_id, role, content),
            )
            conn.execute(
                """
                UPDATE ai_chat_session
                SET updated_at = datetime('now', 'localtime')
                WHERE id = ?
                """,
                (session_id,),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM ai_chat_message WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._row_to_message(row)

    def add_exchange(
        self,
        session_id: str,
        *,
        user_content: str,
        assistant_content: str,
        title_if_empty: str | None = None,
    ) -> tuple[AiChatMessage, AiChatMessage]:
        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                was_empty = (
                    conn.execute(
                        """
                        SELECT 1 FROM ai_chat_message
                        WHERE session_id = ?
                        LIMIT 1
                        """,
                        (session_id,),
                    ).fetchone()
                    is None
                )
                user_cursor = conn.execute(
                    """
                    INSERT INTO ai_chat_message (session_id, role, content)
                    VALUES (?, 'user', ?)
                    """,
                    (session_id, user_content),
                )
                assistant_cursor = conn.execute(
                    """
                    INSERT INTO ai_chat_message (session_id, role, content)
                    VALUES (?, 'assistant', ?)
                    """,
                    (session_id, assistant_content),
                )
                if was_empty and title_if_empty:
                    conn.execute(
                        """
                        UPDATE ai_chat_session
                        SET title = ?, updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """,
                        (title_if_empty.strip() or "新对话", session_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE ai_chat_session
                        SET updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """,
                        (session_id,),
                    )
                user_row = conn.execute(
                    "SELECT * FROM ai_chat_message WHERE id = ?",
                    (user_cursor.lastrowid,),
                ).fetchone()
                assistant_row = conn.execute(
                    "SELECT * FROM ai_chat_message WHERE id = ?",
                    (assistant_cursor.lastrowid,),
                ).fetchone()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return self._row_to_message(user_row), self._row_to_message(assistant_row)

    def list_messages(self, session_id: str) -> list[AiChatMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ai_chat_message WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def recent_messages(self, session_id: str, limit: int) -> list[AiChatMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM ai_chat_message
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, max(0, limit)),
            ).fetchall()
        return [self._row_to_message(row) for row in reversed(rows)]

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> AiChatSession:
        return AiChatSession(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> AiChatMessage:
        return AiChatMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
