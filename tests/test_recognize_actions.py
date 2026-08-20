from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from score_trans.exec.recognize.actions import (
    RecognizeActions,
    _generate_overlay_file_id,
    _register_omr_file,
)
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


class _MxlRecognizer:
    def execute(
        self,
        input_file: str | Path,
        output_dir: str | Path,
        config: ToolConfig,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        del input_file, config, progress_callback
        result = Path(output_dir) / "score.mxl"
        result.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(result, "w") as archive:
            archive.writestr(
                "META-INF/container.xml",
                '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="score.xml"/></rootfiles></container>',
            )
            archive.writestr(
                "score.xml",
                '<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0"/>',
            )
        return result


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


def test_recognize_reads_compressed_mxl_as_musicxml(tmp_path: Path) -> None:
    action = RecognizeActions(
        uploads=_Uploads(),
        settings=_Settings(ToolConfig(work_dir=tmp_path)),
        recognizer=_MxlRecognizer(),
        overlay_service=_OverlayService(),
    )
    source = tmp_path / "5.瑞雪迎春 - 分谱_页面_080.png"
    source.write_bytes(b"image")

    response = action.recognize_from_path(source)

    assert response.musicxml_filename == "score.mxl"
    assert '<score-partwise version="4.0"/>' in response.musicxml_text


def test_recognize_auxiliary_failures_are_logged_and_degraded(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    class BrokenOverlayService:
        def generate_overlay_svgs(self, _output_dir: Path) -> list[Path]:
            raise RuntimeError("overlay failure")

    def fail_rglob(_path: Path, _pattern: str):
        raise OSError("directory failure")

    monkeypatch.setattr(Path, "rglob", fail_rglob)

    assert (
        _generate_overlay_file_id(BrokenOverlayService(), _Uploads(), tmp_path) is None
    )
    assert _register_omr_file(_Uploads(), tmp_path) is None
    assert "生成 Audiveris SVG 叠加层失败" in caplog.text
    assert "查找 Audiveris OMR 文件失败" in caplog.text
