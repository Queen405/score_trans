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
    audiveris_save: bool = True
    audiveris_swap: bool = False
    audiveris_transcribe: bool = False
    audiveris_sheets: str = ""
    audiveris_constants: str = ""
    audiveris_extra_args: str = ""
    audiveris_max_heap: str = "2g"
    audiveris_max_pixel_count: str = "20000000"
