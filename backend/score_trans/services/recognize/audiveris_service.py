from pathlib import Path

from ...domain.parse.musicxml import read_musicxml_text
from ...models.settings.config import ToolConfig
from .external_tools import recognize_with_audiveris


def read_audiveris_musicxml(path: str | Path) -> str:
    """Read either plain MusicXML or Audiveris' compressed MXL output."""
    return read_musicxml_text(Path(path))


class AudiverisService:
    def recognize(
        self, input_file: str | Path, output_dir: str | Path, config: ToolConfig
    ) -> Path:
        return recognize_with_audiveris(Path(input_file), Path(output_dir), config)
