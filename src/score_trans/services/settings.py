from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .env_file import PROJECT_ROOT
from .settings_db import SettingsDB

LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
LOCAL_AUDIVERIS_GRADLE = LOCAL_AUDIVERIS_DIR / "gradlew.bat"


@dataclass(slots=True)
class ToolConfig:
    audiveris_path: str = ""
    java_home: str = ""
    work_dir: Path = Path("work")
    omr_preprocess: bool = True
    omr_preprocess_long_edge: int = 3600
    omr_preprocess_binarize: bool = False

    @classmethod
    def from_db(cls) -> "ToolConfig":
        db = SettingsDB.default()
        default_audiveris = (
            str(LOCAL_AUDIVERIS_GRADLE)
            if LOCAL_AUDIVERIS_GRADLE.exists()
            else "audiveris"
        )
        return cls(
            audiveris_path=db.get("audiveris_path") or default_audiveris,
            java_home=db.get("java_home"),
            work_dir=Path(db.get("work_dir") or str(PROJECT_ROOT / "work")),
            omr_preprocess=db.get_bool("omr_preprocess", True),
            omr_preprocess_long_edge=db.get_int("omr_preprocess_long_edge", 3600),
            omr_preprocess_binarize=db.get_bool("omr_preprocess_binarize", False),
        )
