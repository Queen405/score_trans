from __future__ import annotations

from pathlib import Path

from score_trans.config.settings import (
    AUDIVERIS_PATH,
    JAVA_HOME,
    OMR_PREPROCESS,
    OMR_PREPROCESS_BINARIZE,
    OMR_PREPROCESS_LONG_EDGE,
    WORK_DIR,
)

from ...dao.settings.settings_dao import SettingsDao
from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig


_LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
_LOCAL_AUDIVERIS_GRADLE = _LOCAL_AUDIVERIS_DIR / "gradlew.bat"


def _default_audiveris_path() -> str:
    if AUDIVERIS_PATH:
        return AUDIVERIS_PATH
    return str(_LOCAL_AUDIVERIS_GRADLE) if _LOCAL_AUDIVERIS_GRADLE.exists() else "audiveris"


def _default_work_dir() -> Path:
    if WORK_DIR:
        return Path(WORK_DIR)
    return PROJECT_ROOT / "work"


class SettingsService:
    def __init__(self, dao: SettingsDao | None = None) -> None:
        self.dao = dao or SettingsDao.default()

    def load(self) -> ToolConfig:
        return ToolConfig(
            audiveris_path=self.dao.get("audiveris_path") or _default_audiveris_path(),
            java_home=self.dao.get("java_home") or JAVA_HOME,
            work_dir=Path(self.dao.get("work_dir") or str(_default_work_dir())),
            omr_preprocess=self.dao.get_bool("omr_preprocess", OMR_PREPROCESS),
            omr_preprocess_long_edge=self.dao.get_int("omr_preprocess_long_edge", OMR_PREPROCESS_LONG_EDGE),
            omr_preprocess_binarize=self.dao.get_bool("omr_preprocess_binarize", OMR_PREPROCESS_BINARIZE),
        )

    def get_all(self) -> dict[str, str]:
        return self.dao.get_all()

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.dao.get_bool(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        return self.dao.get_int(key, default)

    def set(self, key: str, value: str) -> None:
        self.dao.set(key, value)
