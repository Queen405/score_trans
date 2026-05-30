from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..domain.musicxml import score_to_jianpu_text
from ..services.file_service import FileService
from ..services.render_service import RenderService
from ..services.settings import ToolConfig
from .convert_to_jianpu import ConvertMusicXmlToJianpuUseCase
from .recognize_score import RecognizeScoreUseCase


@dataclass(slots=True)
class ScorePipelineOutputs:
    input_path: Path
    musicxml_path: Path
    jianpu_text_path: Path
    jianpu_svg_path: Path


class FullPipelineUseCase:
    def __init__(
        self,
        recognizer: RecognizeScoreUseCase | None = None,
        converter: ConvertMusicXmlToJianpuUseCase | None = None,
        renderer: RenderService | None = None,
        file_service: FileService | None = None,
    ) -> None:
        self.recognizer = recognizer or RecognizeScoreUseCase()
        self.converter = converter or ConvertMusicXmlToJianpuUseCase()
        self.renderer = renderer or RenderService()
        self.file_service = file_service or FileService()

    def execute(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        *,
        config: ToolConfig,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> ScorePipelineOutputs:
        source = Path(input_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        recognized = self.recognizer.execute(source, out_dir / "omr", config)
        musicxml_path = _copy_musicxml_output(Path(recognized), out_dir, source.stem)
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
        )
        if title:
            score.title = title
        text_path = out_dir / f"{source.stem}_jianpu.txt"
        self.file_service.write_text(text_path, score_to_jianpu_text(score))
        svg_path = out_dir / f"{source.stem}_jianpu.svg"
        self.renderer.render_score_svg(score, svg_path, title=title or score.title)
        return ScorePipelineOutputs(
            input_path=source,
            musicxml_path=musicxml_path,
            jianpu_text_path=text_path,
            jianpu_svg_path=svg_path,
        )


def _copy_musicxml_output(path: Path, output_dir: Path, stem: str) -> Path:
    suffix = path.suffix if path.suffix.lower() in {".musicxml", ".mxl", ".xml"} else ".musicxml"
    target = output_dir / f"{stem}{suffix}"
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    return target
