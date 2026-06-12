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
from ...models.common.paths import (
    LEGACY_WORK_DIR,
    PROJECT_ROOT,
    USER_CACHE_ROOT,
    USER_WORK_DIR,
)
from ...models.settings.config import ToolConfig


_LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
_LOCAL_AUDIVERIS_GRADLE = _LOCAL_AUDIVERIS_DIR / "gradlew.bat"

# 捆绑的 JDK 路径（打包时由 build-app.py 复制）
_BUNDLED_JDK = PROJECT_ROOT / "third_party" / "jre" / "jdk"


def _default_audiveris_path() -> str:
    if AUDIVERIS_PATH:
        return AUDIVERIS_PATH
    return (
        str(_LOCAL_AUDIVERIS_GRADLE)
        if _LOCAL_AUDIVERIS_GRADLE.exists()
        else "audiveris"
    )


def _default_java_home() -> str:
    """优先使用环境变量配置，否则自动探测捆绑的 JDK 25。"""
    if JAVA_HOME:
        return JAVA_HOME
    if _BUNDLED_JDK.exists() and (_BUNDLED_JDK / "bin" / "java.exe").exists():
        return str(_BUNDLED_JDK)
    # 最后尝试系统 PATH 中的 java
    return ""


def _default_work_dir() -> Path:
    if WORK_DIR:
        return _resolve_work_dir(WORK_DIR)
    return USER_CACHE_ROOT


def _resolve_work_dir(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return _rewrite_legacy_work_dir(path)
    if path == Path("work"):
        return USER_CACHE_ROOT
    return USER_CACHE_ROOT / path


def _rewrite_legacy_work_dir(path: Path) -> Path:
    try:
        relative = path.resolve().relative_to(LEGACY_WORK_DIR.resolve())
    except ValueError:
        try:
            relative = path.resolve().relative_to(USER_WORK_DIR.resolve())
        except ValueError:
            return path
    return USER_CACHE_ROOT / relative


class SettingsService:
    def __init__(self, dao: SettingsDao | None = None) -> None:
        self.dao = dao or SettingsDao.default()

    def load(self) -> ToolConfig:
        return ToolConfig(
            audiveris_path=self.dao.get("audiveris_path") or _default_audiveris_path(),
            java_home=self.dao.get("java_home") or _default_java_home(),
            work_dir=_resolve_work_dir(self.dao.get("work_dir") or _default_work_dir()),
            omr_preprocess=self.dao.get_bool("omr_preprocess", OMR_PREPROCESS),
            omr_preprocess_long_edge=self.dao.get_int(
                "omr_preprocess_long_edge", OMR_PREPROCESS_LONG_EDGE
            ),
            omr_preprocess_binarize=self.dao.get_bool(
                "omr_preprocess_binarize", OMR_PREPROCESS_BINARIZE
            ),
        )

    def get_all(self) -> dict[str, str]:
        return self.dao.get_all()

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.dao.get_bool(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        return self.dao.get_int(key, default)

    def set(self, key: str, value: str) -> None:
        self.dao.set(key, value)
