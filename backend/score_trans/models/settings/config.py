from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ToolConfig:
    audiveris_path: str = ""
    java_home: str = ""
    work_dir: Path = Path("work")
    audiveris_step: str = ""
    audiveris_force: bool = False
    audiveris_save: bool = False
    audiveris_swap: bool = False
    audiveris_transcribe: bool = False
    audiveris_sheets: str = ""
    audiveris_constants: str = ""
    audiveris_extra_args: str = ""
