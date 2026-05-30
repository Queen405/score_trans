from pathlib import Path

from .external_tools import export_with_musescore
from .settings import ToolConfig


class MuseScoreService:
    def export(self, musicxml_file: str | Path, output_file: str | Path, config: ToolConfig) -> Path:
        return export_with_musescore(Path(musicxml_file), Path(output_file), config)
