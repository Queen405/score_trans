from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ...dao.history.history_dao import HistoryDao
from ...models.settings.config import ToolConfig
from ..files.upload_service import UploadService
from ..settings.settings_service import SettingsService

SCRATCH_DIR_NAMES = ("audiveris", "pipeline", "ai_transcribe")


@dataclass(slots=True)
class CacheCleanupResult:
    cache_dir: Path
    before_bytes: int
    after_bytes: int
    freed_bytes: int
    removed_items: int
    preserved_uploads: int


class CacheService:
    def __init__(
        self,
        cache_dir: str | Path | None = None,
        history: HistoryDao | None = None,
        uploads: UploadService | None = None,
    ) -> None:
        self.cache_dir = (
            Path(cache_dir) if cache_dir else SettingsService().load().work_dir
        )
        self.history = history
        self.uploads = uploads or UploadService(ToolConfig(work_dir=self.cache_dir))

    def size_bytes(self) -> int:
        return _path_size(self.cache_dir)

    def clear(self) -> CacheCleanupResult:
        before = self.size_bytes()
        removed_items = 0
        preserved_uploads = 0

        for name in SCRATCH_DIR_NAMES:
            removed_items += _remove_path(self.cache_dir / name)

        uploads_dir = self.cache_dir / "uploads"
        if uploads_dir.is_dir():
            referenced = self._referenced_file_ids()
            prune_result = self.uploads.prune_unreferenced(referenced)
            removed_items += prune_result.removed_items
            preserved_uploads += prune_result.preserved_uploads

        after = self.size_bytes()
        return CacheCleanupResult(
            cache_dir=self.cache_dir,
            before_bytes=before,
            after_bytes=after,
            freed_bytes=max(0, before - after),
            removed_items=removed_items,
            preserved_uploads=preserved_uploads,
        )

    def _referenced_file_ids(self) -> set[str]:
        history = self.history or HistoryDao()
        return history.referenced_file_ids()


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _remove_path(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError:
        return 0
    return 1
