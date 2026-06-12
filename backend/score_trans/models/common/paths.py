from __future__ import annotations

import os
import sys
from pathlib import Path

USER_DATA_DIR_ENV = "SCORE_TRANS_DATA_DIR"
CACHE_DIR_ENV = "SCORE_TRANS_CACHE_DIR"
USER_DATA_DIR_NAME = ".sorce_trans"
CACHE_DIR_NAME = "cache"

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：backend.exe 位于 <app>/resources/backend/
    # PROJECT_ROOT 指向 <app>/resources/，与开发模式的项目根目录等价
    PROJECT_ROOT = Path(sys.executable).resolve().parent.parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_user_data_root() -> Path:
    configured = os.getenv(USER_DATA_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / USER_DATA_DIR_NAME).resolve()


def _resolve_cache_root() -> Path:
    configured = os.getenv(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return USER_DATA_ROOT / CACHE_DIR_NAME


USER_DATA_ROOT = _resolve_user_data_root()
USER_CACHE_ROOT = _resolve_cache_root()
USER_WORK_DIR = USER_DATA_ROOT / "work"
LEGACY_WORK_DIR = PROJECT_ROOT / "work"
