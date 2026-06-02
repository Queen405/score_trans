from __future__ import annotations

from pathlib import Path

from ...dao.settings.settings_dao import SettingsDao
from ...models.common.paths import PROJECT_ROOT
from ...models.settings.config import ToolConfig


LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
LOCAL_AUDIVERIS_GRADLE = LOCAL_AUDIVERIS_DIR / "gradlew.bat"


class SettingsService:
    def __init__(self, dao: SettingsDao | None = None) -> None:
        self.dao = dao or SettingsDao.default()

    def load(self) -> ToolConfig:
        default_audiveris = (
            str(LOCAL_AUDIVERIS_GRADLE)
            if LOCAL_AUDIVERIS_GRADLE.exists()
            else "audiveris"
        )
        return ToolConfig(
            audiveris_path=self.dao.get("audiveris_path") or default_audiveris,
            java_home=self.dao.get("java_home"),
            work_dir=Path(self.dao.get("work_dir") or str(PROJECT_ROOT / "work")),
            omr_preprocess=self.dao.get_bool("omr_preprocess", True),
            omr_preprocess_long_edge=self.dao.get_int("omr_preprocess_long_edge", 3600),
            omr_preprocess_binarize=self.dao.get_bool("omr_preprocess_binarize", False),
        )

    def get_all(self) -> dict[str, str]:
        return self.dao.get_all()

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.dao.get_bool(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        return self.dao.get_int(key, default)

    def set(self, key: str, value: str) -> None:
        self.dao.set(key, value)
