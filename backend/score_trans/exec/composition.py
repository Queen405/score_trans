from __future__ import annotations

from functools import lru_cache

from ..services.files.file_service import FileService
from ..services.files.upload_service import UploadService
from ..services.history.history_service import HistoryService
from ..services.settings.settings_service import SettingsService


@lru_cache(maxsize=1)
def shared_uploads() -> UploadService:
    return UploadService()


@lru_cache(maxsize=1)
def shared_file_service() -> FileService:
    return FileService()


@lru_cache(maxsize=1)
def shared_history_service() -> HistoryService:
    return HistoryService()


@lru_cache(maxsize=1)
def shared_settings_service() -> SettingsService:
    return SettingsService()
