from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .env_file import PROJECT_ROOT, load_project_env

LOCAL_AUDIVERIS_DIR = PROJECT_ROOT / "third_party" / "audiveris"
LOCAL_AUDIVERIS_GRADLE = LOCAL_AUDIVERIS_DIR / "gradlew.bat"
DEFAULT_JAVA_HOME = Path(r"E:\ENV\JAVA\JDK25")


@dataclass(slots=True)
class ToolConfig:
    audiveris_path: str = ""
    musescore_path: str = ""
    java_home: str = ""
    work_dir: Path = Path("work")
    omr_preprocess: bool = True
    omr_preprocess_long_edge: int = 3600
    omr_preprocess_binarize: bool = False

    @classmethod
    def from_env(cls) -> "ToolConfig":
        load_project_env()
        default_audiveris = (
            str(LOCAL_AUDIVERIS_GRADLE)
            if LOCAL_AUDIVERIS_GRADLE.exists()
            else "audiveris"
        )
        return cls(
            audiveris_path=os.environ.get("SCORE_TRANS_AUDIVERIS", default_audiveris),
            musescore_path=os.environ.get("SCORE_TRANS_MUSESCORE", "musescore"),
            java_home=os.environ.get(
                "SCORE_TRANS_JAVA_HOME",
                str(DEFAULT_JAVA_HOME) if (DEFAULT_JAVA_HOME / "bin" / "java.exe").exists() else "",
            ),
            work_dir=Path(os.environ.get("SCORE_TRANS_WORKDIR", str(PROJECT_ROOT / "work"))),
            omr_preprocess=_env_bool("SCORE_TRANS_OMR_PREPROCESS", True),
            omr_preprocess_long_edge=_env_int("SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE", 3600),
            omr_preprocess_binarize=_env_bool("SCORE_TRANS_OMR_PREPROCESS_BINARIZE", False),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return max(0, int(value))
    except ValueError:
        return default
