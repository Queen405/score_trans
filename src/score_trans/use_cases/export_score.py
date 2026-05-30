from pathlib import Path

from ..services.musescore_service import MuseScoreService
from ..services.settings import ToolConfig


class ExportScoreUseCase:
    def __init__(self, musescore_service: MuseScoreService | None = None) -> None:
        self.musescore_service = musescore_service or MuseScoreService()

    def execute(self, musicxml_file: str | Path, output_file: str | Path, config: ToolConfig) -> Path:
        return self.musescore_service.export(musicxml_file, output_file, config)
