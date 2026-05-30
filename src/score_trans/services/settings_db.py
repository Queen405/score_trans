from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .env_file import PROJECT_ROOT, load_project_env

DEFAULT_DB_PATH = PROJECT_ROOT / "work" / "settings.db"


class SettingsDB:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ocr_settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # Seed from .env / environment if table is empty
            existing = conn.execute("SELECT COUNT(*) AS n FROM ocr_settings").fetchone()
            if existing["n"] == 0:
                load_project_env()
                defaults = [
                    ("ocr_api_key", os.environ.get("SCORE_TRANS_OCR_API_KEY", "")),
                    ("ocr_base_url", os.environ.get("SCORE_TRANS_OCR_BASE_URL", "https://api.siliconflow.cn/v1")),
                    ("ocr_model", os.environ.get("SCORE_TRANS_OCR_MODEL", "deepseek-ai/DeepSeek-OCR")),
                ]
                conn.executemany(
                    "INSERT INTO ocr_settings (key, value) VALUES (?, ?)",
                    defaults,
                )
                conn.commit()

    def get(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM ocr_settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO ocr_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            conn.commit()

    def get_all(self) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM ocr_settings").fetchall()
        return {row["key"]: row["value"] for row in rows}
