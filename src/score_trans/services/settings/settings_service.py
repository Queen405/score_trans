from __future__ import annotations

import os
from pathlib import Path

from ...dao.settings.settings_dao import SettingsDao
from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig


_LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
_LOCAL_AUDIVERIS_GRADLE = _LOCAL_AUDIVERIS_DIR / "gradlew.bat"


def _default_audiveris_path() -> str:
    env = os.getenv("SCORE_TRANS_AUDIVERIS", "")
    if env:
        return env
    return str(_LOCAL_AUDIVERIS_GRADLE) if _LOCAL_AUDIVERIS_GRADLE.exists() else "audiveris"


def _default_work_dir() -> Path:
    env = os.getenv("SCORE_TRANS_WORKDIR", "")
    if env:
        return Path(env)
    return PROJECT_ROOT / "work"


class SettingsService:
    def __init__(self, dao: SettingsDao | None = None) -> None:
        self.dao = dao or SettingsDao.default()

    def load(self) -> ToolConfig:
        return ToolConfig(
            audiveris_path=self.dao.get("audiveris_path") or _default_audiveris_path(),
            java_home=self.dao.get("java_home") or os.getenv("SCORE_TRANS_JAVA_HOME", ""),
            work_dir=Path(self.dao.get("work_dir") or str(_default_work_dir())),
            omr_preprocess=self.dao.get_bool("omr_preprocess", os.getenv("SCORE_TRANS_OMR_PREPROCESS", "1").lower() in ("1", "true", "yes", "on")),
            omr_preprocess_long_edge=self.dao.get_int("omr_preprocess_long_edge", int(os.getenv("SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE", "3600"))),
            omr_preprocess_binarize=self.dao.get_bool("omr_preprocess_binarize", os.getenv("SCORE_TRANS_OMR_PREPROCESS_BINARIZE", "0").lower() in ("1", "true", "yes", "on")),
        )

    def get_all(self) -> dict[str, str]:
        return self.dao.get_all()

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.dao.get_bool(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        return self.dao.get_int(key, default)

    def set(self, key: str, value: str) -> None:
        self.dao.set(key, value)
