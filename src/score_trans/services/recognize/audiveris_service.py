from pathlib import Path

from ...models.settings.config import ToolConfig
from .external_tools import recognize_with_audiveris


class AudiverisService:
    def recognize(self, input_file: str | Path, output_dir: str | Path, config: ToolConfig) -> Path:
        return recognize_with_audiveris(Path(input_file), Path(output_dir), config)
