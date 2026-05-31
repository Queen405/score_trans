from __future__ import annotations

from pathlib import Path

from ..domain.models import JianpuScore
from ..services.export_service import ExportService
from .convert_to_jianpu import ConvertMusicXmlToJianpuUseCase


class ExportScoreUseCase:
    def __init__(
        self,
        converter: ConvertMusicXmlToJianpuUseCase | None = None,
        export_service: ExportService | None = None,
    ) -> None:
        self.converter = converter or ConvertMusicXmlToJianpuUseCase()
        self.export_service = export_service or ExportService()

    def execute(
        self,
        musicxml_file: str | Path,
        output_file: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> Path:
        musicxml_path = Path(musicxml_file)
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
        )
        if title:
            score.title = title

        return self.export_service.export(score, output_path, title=title)

    def execute_from_score(
        self,
        score: JianpuScore,
        output_file: str | Path,
        title: str | None = None,
    ) -> Path:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return self.export_service.export(score, output_path, title=title)
