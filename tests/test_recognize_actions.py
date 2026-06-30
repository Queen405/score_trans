from __future__ import annotations

from pathlib import Path

from score_trans.exec.recognize.actions import RecognizeActions
from score_trans.models.settings.config import ToolConfig
from score_trans.models.tasks.entities import ProgressCallback


class _Settings:
    def __init__(self, config: ToolConfig) -> None:
        self.config = config

    def load(self) -> ToolConfig:
        return self.config


class _Recognizer:
    def __init__(self) -> None:
        self.output_dirs: list[Path] = []

    def execute(
        self,
        input_file: str | Path,
        output_dir: str | Path,
        config: ToolConfig,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        del input_file, config, progress_callback
        resolved_output = Path(output_dir)
        self.output_dirs.append(resolved_output)
        resolved_output.mkdir(parents=True, exist_ok=True)
        result = resolved_output / "score.musicxml"
        result.write_text("<score-partwise/>", encoding="utf-8")
        return result


class _OverlayService:
    def __init__(self) -> None:
        self.output_dirs: list[Path] = []

    def generate_overlay_svgs(self, output_dir: str | Path) -> list[Path]:
        self.output_dirs.append(Path(output_dir))
        return []


class _Uploads:
    def register(self, path: str | Path) -> str:
        return Path(path).name


def test_recognize_calls_use_isolated_audiveris_directories(tmp_path: Path) -> None:
    recognizer = _Recognizer()
    overlay_service = _OverlayService()
    action = RecognizeActions(
        uploads=_Uploads(),
        settings=_Settings(ToolConfig(work_dir=tmp_path)),
        recognizer=recognizer,
        overlay_service=overlay_service,
    )
    source = tmp_path / "score.png"
    source.write_bytes(b"image")

    action.recognize_from_path(source)
    action.recognize_from_path(source)

    assert len(recognizer.output_dirs) == 2
    assert recognizer.output_dirs[0] != recognizer.output_dirs[1]
    assert all(path.parent == tmp_path / "audiveris" for path in recognizer.output_dirs)
    assert overlay_service.output_dirs == recognizer.output_dirs
