from __future__ import annotations

import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import UploadFile

from ..services.settings import ToolConfig


class UploadManager:
    """Manages uploaded files: save, lookup, register, cleanup."""

    def __init__(self, config: ToolConfig | None = None) -> None:
        self.config = config or ToolConfig.from_env()
        self.base_dir = self.config.work_dir / "uploads"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, Path] = {}
        self._lock = threading.Lock()

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
        return file_id

    def register(self, path: Path) -> str:
        """Register an existing local file and return its file_id."""
        file_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._files[file_id] = Path(path)
        return file_id

    def get_path(self, file_id: str) -> Path | None:
        """Look up a file_id and return the local Path, or None."""
        with self._lock:
            return self._files.get(file_id)

    def cleanup(self, file_id: str) -> None:
        """Remove a file entry and its upload directory if applicable."""
        with self._lock:
            path = self._files.pop(file_id, None)

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
                shutil.rmtree(entry, ignore_errors=True)
                cleaned += 1
        return cleaned

    def get_size(self, file_id: str) -> int | None:
        """Return file size in bytes, or None if not found."""
        path = self.get_path(file_id)
        if path and path.exists():
            return path.stat().st_size
        return None
