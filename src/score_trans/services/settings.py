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
        )
