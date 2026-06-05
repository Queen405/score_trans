"""Environment / dotenv loading utilities."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import CONFIG_DIR
from ..models.common.paths import PROJECT_ROOT

DISABLE_DOTENV_ENV = "SCORE_TRANS_DISABLE_DOTENV"


def load_project_env(path: str | Path | None = None, *, override: bool = False) -> None:
    """Load key=value pairs from a .env file into os.environ."""
    if path is None and os.environ.get(DISABLE_DOTENV_ENV):
        return

    if path is not None:
        env_path = Path(path)
    else:
        env_path = CONFIG_DIR / ".env"
        if not env_path.is_file():
            env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or (not override and key in os.environ):
            continue
        os.environ[key] = _unquote_env_value(value.strip())


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value
