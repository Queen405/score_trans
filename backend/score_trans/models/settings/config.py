from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolConfig:
    audiveris_path: str = ""
    java_home: str = ""
    work_dir: Path = Path("work")
