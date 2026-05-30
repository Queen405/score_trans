from pathlib import Path

from ..services.audiveris_service import AudiverisService
from ..services.settings import ToolConfig


class RecognizeScoreUseCase:
    def __init__(self, audiveris_service: AudiverisService | None = None) -> None:
        self.audiveris_service = audiveris_service or AudiverisService()

    def execute(self, input_file: str | Path, output_dir: str | Path, config: ToolConfig) -> Path:
        return self.audiveris_service.recognize(input_file, output_dir, config)
