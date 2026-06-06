from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import UploadFile

from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig
from ..settings.settings_service import SettingsService


class UploadService:
    """Manages uploaded files: save, lookup, register, cleanup."""

    def __init__(self, config: ToolConfig | None = None) -> None:
        self.config = config or SettingsService().load()
        work_dir = self.config.work_dir
        if not work_dir.is_absolute():
            work_dir = PROJECT_ROOT / work_dir
        self.base_dir = (work_dir / "uploads").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.base_dir / "index.json"
        self._files: dict[str, Path] = {}
        self._lock = threading.Lock()
        self._load_index()

    def _load_index(self) -> None:
        if not self._index_path.exists():
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

    def _resolve_index_path(self, path: Path) -> Path:
        if path.is_absolute():
            return path.resolve()

        project_path = PROJECT_ROOT / path
        if project_path.exists():
            return project_path.resolve()

        return path.resolve()

    def _persist_index(self) -> None:
        with self._lock:
            serializable = {
                file_id: str(path.resolve())
                for file_id, path in self._files.items()
                if path.exists()
            }
            self._files = {file_id: Path(path) for file_id, path in serializable.items()}

        try:
            tmp_path = self._index_path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(self._index_path)
        except OSError:
            # Persistence is best-effort; runtime behavior still relies on memory and fallback scan.
            return

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

        candidates = sorted((p for p in fallback_dir.iterdir() if p.is_file()), key=lambda p: p.name)
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
        self._persist_index()

        if path is None:
            return

        # Only delete upload subdirectories, not arbitrary paths
        if path.parent.parent == self.base_dir and path.parent != self.base_dir:
            shutil.rmtree(path.parent, ignore_errors=True)

    def cleanup_old(self, max_age_hours: int = 24) -> int:
        """Remove upload directories older than max_age_hours. Returns count cleaned."""
        cutoff = time.time() - max_age_hours * 3600
        cleaned = 0
        for entry in self.base_dir.iterdir():
            if entry.is_dir() and entry.stat().st_mtime < cutoff:
                # Remove from mapping
                with self._lock:
                    to_remove = [fid for fid, p in self._files.items() if p.is_relative_to(entry)]
                    for fid in to_remove:
                        self._files.pop(fid, None)
                self._persist_index()
                shutil.rmtree(entry, ignore_errors=True)
                cleaned += 1
        return cleaned

    def get_size(self, file_id: str) -> int | None:
        """Return file size in bytes, or None if not found."""
        path = self.get_path(file_id)
        if path and path.exists():
            return path.stat().st_size
        return None
