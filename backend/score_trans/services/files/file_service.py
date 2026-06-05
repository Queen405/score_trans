from pathlib import Path

from ...domain.musicxml import read_musicxml_text


class FileService:
    def read_text(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_text(self, path: str | Path, text: str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def read_musicxml_text(self, path: str | Path) -> str:
        return read_musicxml_text(Path(path))
