from pathlib import Path

from ..domain.jianpu import jianpu_file_to_musicxml, jianpu_to_musicxml


class ConvertJianpuToMusicXmlUseCase:
    def execute_text(self, jianpu_text: str, *, title: str = "Jianpu Import") -> str:
        return jianpu_to_musicxml(jianpu_text, title=title)

    def execute_file(self, input_path: str | Path, *, title: str = "Jianpu Import") -> str:
        return jianpu_file_to_musicxml(Path(input_path), title=title)
