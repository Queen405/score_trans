from __future__ import annotations

import sqlite3
from pathlib import Path

from score_trans.config.settings import (
    AI_API_KEY,
    AI_BASE_URL,
    AI_MODEL,
    AI_PROVIDER,
    ASSISTANT_API_KEY,
    ASSISTANT_BASE_URL,
    ASSISTANT_MODEL,
    ASSISTANT_PROVIDER,
    AUDIVERIS_MAX_HEAP,
    AUDIVERIS_MAX_PIXEL_COUNT,
    AUDIVERIS_PATH,
    JAVA_HOME,
    OCR_API_KEY,
    OCR_BASE_URL,
    OCR_FALLBACK_MODEL,
    OCR_MODEL,
    OCR_PROVIDER,
    OUTPUT_DIR,
)

from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "settings.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "settings.db"

TABLE_NAME = "settings"

_DEFAULTS: dict[str, str] = {
    "audiveris_path": AUDIVERIS_PATH,
    "java_home": JAVA_HOME,
    "audiveris_max_heap": AUDIVERIS_MAX_HEAP,
    "audiveris_max_pixel_count": AUDIVERIS_MAX_PIXEL_COUNT,
    "output_dir": OUTPUT_DIR,
    "target_key": "C",
    "show_measure_numbers": "1",
    "measure_number_mode": "all",
    "confirm_start_measure_number": "1",
    "jianpu_syntax_highlight": "0",
    "accidental_mode": "auto",
    "ocr_provider": OCR_PROVIDER,
    "ocr_api_key": OCR_API_KEY,
    "ocr_base_url": OCR_BASE_URL,
    "ocr_model": OCR_MODEL,
    "ocr_fallback_model": OCR_FALLBACK_MODEL,
    "ai_provider": AI_PROVIDER,
    "ai_api_key": AI_API_KEY,
    "ai_base_url": AI_BASE_URL,
    "ai_model": AI_MODEL,
    "assistant_provider": ASSISTANT_PROVIDER,
    "assistant_api_key": ASSISTANT_API_KEY,
    "assistant_base_url": ASSISTANT_BASE_URL,
    "assistant_model": ASSISTANT_MODEL,
}


class SettingsDao:
    _instance: "SettingsDao | None" = None

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if db_path is None:
            migrate_legacy_sqlite(self.db_path, LEGACY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def default(cls) -> "SettingsDao":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._migrate_old_table(conn)
            self._migrate_measure_number_mode(conn)
            for key, value in _DEFAULTS.items():
                conn.execute(
                    f"INSERT OR IGNORE INTO {TABLE_NAME} (key, value) VALUES (?, ?)",
                    (key, value),
                )
            conn.commit()

    def _migrate_old_table(self, conn: sqlite3.Connection) -> None:
        try:
            rows = conn.execute("SELECT key, value FROM ocr_settings").fetchall()
        except sqlite3.OperationalError:
            return
        for row in rows:
            conn.execute(
                f"INSERT OR IGNORE INTO {TABLE_NAME} (key, value) VALUES (?, ?)",
                (row["key"], row["value"]),
            )
        conn.execute("DROP TABLE IF EXISTS ocr_settings")

    def _migrate_measure_number_mode(self, conn: sqlite3.Connection) -> None:
        mode = conn.execute(
            f"SELECT value FROM {TABLE_NAME} WHERE key = ?", ("measure_number_mode",)
        ).fetchone()
        if mode is not None:
            return
        show = conn.execute(
            f"SELECT value FROM {TABLE_NAME} WHERE key = ?", ("show_measure_numbers",)
        ).fetchone()
        value = "all"
        if show is not None and show["value"].strip().lower() in {
            "0",
            "false",
            "no",
            "off",
            "",
        }:
            value = "none"
        conn.execute(
            f"INSERT INTO {TABLE_NAME} (key, value) VALUES (?, ?)",
            ("measure_number_mode", value),
        )

    def get(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT value FROM {TABLE_NAME} WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {TABLE_NAME} (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def get_all(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT key, value FROM {TABLE_NAME}").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, "")
        if not value:
            return default
        return value.strip().lower() not in {"0", "false", "no", "off", ""}

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, "")
        if not value:
            return default
        try:
            return max(0, int(value))
        except ValueError:
            return default
