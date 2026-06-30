from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import UploadFile

from ...models.common.paths import (
    LEGACY_WORK_DIR,
    PROJECT_ROOT,
    USER_CACHE_ROOT,
    USER_WORK_DIR,
)
from ...models.settings.config import ToolConfig
from .image_info import strip_image_metadata
from ..settings.settings_service import SettingsService


_INDEX_LOCK = threading.Lock()
_INDEX_CACHE: dict[Path, tuple[int, int, dict[str, Path]]] = {}
_MIGRATION_LOCK = threading.Lock()
_MIGRATED_UPLOAD_DIRS: set[Path] = set()


class UploadService:
    """Manages uploaded files: save, lookup, register, cleanup."""

    def __init__(self, config: ToolConfig | None = None) -> None:
        migrate_legacy = config is None
        self.config = config or SettingsService().load()
        work_dir = self.config.work_dir
        if not work_dir.is_absolute():
            work_dir = USER_CACHE_ROOT / work_dir
        self.base_dir = (work_dir / "uploads").resolve()
        if migrate_legacy:
            _migrate_legacy_uploads_once(self.base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.base_dir / "index.json"
        self._files: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._load_index()

    def _load_index(self) -> None:
        if not self._index_path.exists():
            return

        stat = self._index_path.stat()
        cache_key = (stat.st_mtime_ns, stat.st_size)
        with _INDEX_LOCK:
            cached = _INDEX_CACHE.get(self._index_path)
            if cached and cached[0] == cache_key[0] and cached[1] == cache_key[1]:
                with self._lock:
                    self._files = dict(cached[2])
                return

        try:
            raw = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(raw, dict):
            return

        restored: dict[str, Path] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            path = self._resolve_index_path(Path(value))
            if path.exists():
                restored[key] = path

        with self._lock:
            self._files = restored

        with _INDEX_LOCK:
            _INDEX_CACHE[self._index_path] = (
                cache_key[0],
                cache_key[1],
                dict(restored),
            )

    def _resolve_index_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path.resolve()

        cache_path = USER_CACHE_ROOT / path
        if cache_path.exists():
            return cache_path.resolve()

        project_path = PROJECT_ROOT / path
        if project_path.exists():
            return project_path.resolve()

        return path.resolve()

    def _persist_index(self, *, remove_ids: set[str] | None = None) -> None:
        remove_ids = remove_ids or set()
        with self._lock:
            current = {
                file_id: str(path.resolve())
                for file_id, path in self._files.items()
                if file_id not in remove_ids and path.exists()
            }

        with _INDEX_LOCK:
            existing = _read_index(self._index_path)
            serializable = {
                **existing,
                **current,
            }
            serializable = {
                file_id: path
                for file_id, path in serializable.items()
                if file_id not in remove_ids and Path(path).exists()
            }

            try:
                tmp_path = self._index_path.with_suffix(".tmp")
                tmp_path.write_text(
                    json.dumps(serializable, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                tmp_path.replace(self._index_path)
                stat = self._index_path.stat()
                _INDEX_CACHE[self._index_path] = (
                    stat.st_mtime_ns,
                    stat.st_size,
                    {file_id: Path(path) for file_id, path in serializable.items()},
                )
            except OSError:
                # Persistence is best-effort; runtime behavior still relies on memory and fallback scan.
                return

        with self._lock:
            self._files = {
                file_id: Path(path) for file_id, path in serializable.items()
            }

    def save(self, upload_file: UploadFile) -> str:
        """Save an uploaded file and return its file_id."""
        file_id = uuid.uuid4().hex[:12]
        file_dir = self.base_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)

        filename = upload_file.filename or "upload"
        # Sanitize filename
        safe_name = Path(filename).name
        target = file_dir / safe_name

        with target.open("wb") as f:
            shutil.copyfileobj(upload_file.file, f)

        strip_image_metadata(target)

        with self._lock:
            self._files[file_id] = target
        self._persist_index()
        return file_id

    def register(self, path: Path) -> str:
        """Register an existing local file and return its file_id."""
        src_path = self._resolve_index_path(Path(path))
        if not src_path.exists():
            raise FileNotFoundError(f"文件不存在，无法注册：{src_path}")

        file_id = uuid.uuid4().hex[:12]
        file_dir = self.base_dir / file_id
        file_dir.mkdir(parents=True, exist_ok=True)

        safe_name = Path(src_path.name).name or "file"
        target = file_dir / safe_name

        if src_path.resolve() != target.resolve():
            if src_path.parent == self.base_dir:
                shutil.move(str(src_path), str(target))
            else:
                shutil.copy2(src_path, target)

        with self._lock:
            self._files[file_id] = target
        self._persist_index()
        return file_id

    def get_path(self, file_id: str) -> Path | None:
        """Look up a file_id and return the local Path, or None."""
        with self._lock:
            path = self._files.get(file_id)

        if path and path.exists():
            return path

        if path and not path.exists():
            with self._lock:
                self._files.pop(file_id, None)
            self._persist_index()

        fallback_dir = self.base_dir / file_id
        if not fallback_dir.is_dir():
            return None

        candidates = sorted(
            (p for p in fallback_dir.iterdir() if p.is_file()), key=lambda p: p.name
        )
        if not candidates:
            return None

        restored = candidates[0]
        with self._lock:
            self._files[file_id] = restored
        self._persist_index()
        return restored

    def cleanup(self, file_id: str) -> None:
        """Remove a file entry and its upload directory if applicable."""
        with self._lock:
            path = self._files.pop(file_id, None)
        self._persist_index(remove_ids={file_id})

        if path is None:
            return

        # Only delete upload subdirectories, not arbitrary paths
        if path.parent.parent == self.base_dir and path.parent != self.base_dir:
            shutil.rmtree(path.parent, ignore_errors=True)

    def exists_many(self, file_ids: list[str]) -> dict[str, bool]:
        """Return existence for multiple file IDs with one UploadService/index load."""
        return {file_id: self.get_path(file_id) is not None for file_id in file_ids}


def _read_index(index_path: Path) -> dict[str, str]:
    if not index_path.exists():
        return {}
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _migrate_legacy_uploads(target: Path) -> None:
    for legacy in (LEGACY_WORK_DIR / "uploads", USER_WORK_DIR / "uploads"):
        if not legacy.is_dir() or _same_path(target, legacy):
            continue

        target.mkdir(parents=True, exist_ok=True)
        try:
            for child in legacy.iterdir():
                if child.name == "index.json":
                    continue
                destination = target / child.name
                if destination.exists():
                    continue
                if child.is_dir():
                    shutil.copytree(child, destination)
                elif child.is_file():
                    shutil.copy2(child, destination)
        except OSError:
            continue


def _migrate_legacy_uploads_once(target: Path) -> None:
    resolved_target = target.resolve()
    with _MIGRATION_LOCK:
        if resolved_target in _MIGRATED_UPLOAD_DIRS:
            return
        _migrate_legacy_uploads(resolved_target)
        _MIGRATED_UPLOAD_DIRS.add(resolved_target)


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False
