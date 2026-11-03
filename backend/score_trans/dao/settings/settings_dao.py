from __future__ import annotations

import math

import sqlite3
from collections.abc import Mapping
from pathlib import Path

from ...models.common.paths import LEGACY_WORK_DIR, USER_WORK_DIR
from ..storage import migrate_legacy_sqlite

DEFAULT_DB_PATH = USER_WORK_DIR / "settings.db"
LEGACY_DB_PATH = LEGACY_WORK_DIR / "settings.db"

TABLE_NAME = "settings"
_OBSOLETE_KEYS = ("confirm_start_measure_number",)


class SettingsDao:
    _instance: "SettingsDao | None" = None

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        defaults: Mapping[str, str] | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.defaults = dict(defaults or {})
        if db_path is None:
            migrate_legacy_sqlite(self.db_path, LEGACY_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def default(
        cls,
        defaults: Mapping[str, str] | None = None,
    ) -> "SettingsDao":
        if cls._instance is None:
            cls._instance = cls(defaults=defaults)
        elif defaults and any(
            cls._instance.defaults.get(key) != value for key, value in defaults.items()
        ):
            cls._instance.ensure_defaults(defaults)
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
            for key, value in self.defaults.items():
                conn.execute(
                    f"INSERT OR IGNORE INTO {TABLE_NAME} (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._remove_obsolete_settings(conn)
            conn.commit()

    def ensure_defaults(self, defaults: Mapping[str, str]) -> None:
        with self._connect() as conn:
            for key, value in defaults.items():
                conn.execute(
                    f"INSERT OR IGNORE INTO {TABLE_NAME} (key, value) VALUES (?, ?)",
                    (key, value),
                )
            self._remove_obsolete_settings(conn)
            conn.commit()
        self.defaults.update(defaults)

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

    @staticmethod
    def _remove_obsolete_settings(conn: sqlite3.Connection) -> None:
        placeholders = ", ".join("?" for _ in _OBSOLETE_KEYS)
        conn.execute(
            f"DELETE FROM {TABLE_NAME} WHERE key IN ({placeholders})",
            _OBSOLETE_KEYS,
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

    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self.get(key, "")
        if not value:
            return default
        try:
            parsed = float(value)
        except ValueError:
            return default
        return parsed if math.isfinite(parsed) else default

    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, "")
        if not value:
            return default
        try:
            return max(0, int(value))
        except ValueError:
            return default
