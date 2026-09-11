from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

USER_DATA_DIR_ENV = "SCORE_TRANS_DATA_DIR"
CACHE_DIR_ENV = "SCORE_TRANS_CACHE_DIR"
USER_DATA_DIR_NAME = ".score_trans"
LEGACY_USER_DATA_DIR_NAME = ".sorce_trans"
CACHE_DIR_NAME = "cache"

if getattr(sys, "frozen", False):
    # PyInstaller 打包模式：可执行文件位于 <app>/resources/backend/
    # PROJECT_ROOT 指向 <app>/resources/，与开发模式的项目根目录等价
    CONFIG_DIR = Path(sys.executable).resolve().parent
    PROJECT_ROOT = Path(sys.executable).resolve().parent.parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[4]
    CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def java_binary_name() -> str:
    """JDK bin/ 下的 java 可执行文件名（Windows 带 .exe，其他平台无后缀）。"""
    return "java.exe" if sys.platform == "win32" else "java"


def gradlew_script_name() -> str:
    """Gradle wrapper 脚本名（Windows 用 .bat，其他平台用 sh 版）。"""
    return "gradlew.bat" if sys.platform == "win32" else "gradlew"


def migrate_legacy_user_data_directory(legacy: Path, target: Path) -> bool:
    """Copy missing legacy user data without overwriting or deleting either tree."""
    if not legacy.exists():
        return True
    try:
        if legacy.resolve() == target.resolve():
            return True
        if legacy.is_symlink() or not legacy.is_dir():
            return False
        target.mkdir(parents=True, exist_ok=True)
        return _copy_missing_directory_contents(legacy, target)
    except OSError:
        return False


def _copy_missing_directory_contents(source: Path, target: Path) -> bool:
    succeeded = True
    for source_child in source.iterdir():
        target_child = target / source_child.name
        if source_child.is_symlink():
            succeeded = False
            continue
        if source_child.is_dir():
            if target_child.exists() and not target_child.is_dir():
                continue
            try:
                target_child.mkdir(parents=True, exist_ok=True)
                child_succeeded = _copy_missing_directory_contents(
                    source_child, target_child
                )
            except OSError:
                child_succeeded = False
            succeeded = child_succeeded and succeeded
            continue
        if source_child.is_file():
            succeeded = _copy_file_if_missing(source_child, target_child) and succeeded
            continue
        succeeded = False
    return succeeded


def _copy_file_if_missing(source: Path, target: Path) -> bool:
    if target.exists():
        return True
    created = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as source_file:
            try:
                target_file = target.open("xb")
            except FileExistsError:
                return True
            created = True
            with target_file:
                shutil.copyfileobj(source_file, target_file)
        try:
            shutil.copystat(source, target, follow_symlinks=False)
        except OSError:
            pass
        return True
    except OSError:
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
        return False


def _resolve_user_data_root() -> Path:
    configured = os.getenv(USER_DATA_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    target = (Path.home() / USER_DATA_DIR_NAME).resolve()
    legacy = (Path.home() / LEGACY_USER_DATA_DIR_NAME).resolve()
    target_existed = target.exists()
    migrated = migrate_legacy_user_data_directory(legacy, target)
    if not migrated and not target_existed and legacy.exists():
        return legacy
    return target


def _resolve_cache_root() -> Path:
    configured = os.getenv(CACHE_DIR_ENV, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return USER_DATA_ROOT / CACHE_DIR_NAME


USER_DATA_ROOT = _resolve_user_data_root()
USER_CACHE_ROOT = _resolve_cache_root()
USER_WORK_DIR = USER_DATA_ROOT / "work"
LEGACY_WORK_DIR = PROJECT_ROOT / "work"
