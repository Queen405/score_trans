from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ...domain.musicxml import score_to_jianpu_text
from ...models.pipeline.schemas import PipelineResponse
from ...models.settings.config import ToolConfig
from ...services.files.file_service import FileService
from ...services.files.image_info import image_dimensions
from ...services.files.upload_service import UploadService
from ...services.ocr.provider import OCRProvider
from ...services.recognize.image_preprocessing import IMAGE_SUFFIXES
from ...services.render.render_service import RenderService
from ...services.settings.settings_service import SettingsService
from ..convert.actions import MusicXmlToJianpuAction
from ..recognize.actions import RecognizeScoreAction


@dataclass(slots=True)
class ScorePipelineOutputs:
    input_path: Path
    musicxml_path: Path
    jianpu_text_path: Path
    jianpu_svg_path: Path


class FullPipelineAction:
    def __init__(
        self,
        recognizer: RecognizeScoreAction | None = None,
        converter: MusicXmlToJianpuAction | None = None,
        renderer: RenderService | None = None,
        file_service: FileService | None = None,
    ) -> None:
        self.recognizer = recognizer or RecognizeScoreAction()
        self.converter = converter or MusicXmlToJianpuAction()
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
        ocr_provider: OCRProvider | None = None,
    ) -> ScorePipelineOutputs:
        source = Path(input_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        recognized = self.recognizer.execute(source, out_dir / "omr", config)
        musicxml_path = _copy_musicxml_output(Path(recognized), out_dir, source.stem)
        ocr_image_path = source if _is_ocr_image(source) else None
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            image_path=ocr_image_path,
            ocr_provider=ocr_provider,
        )
        if title:
            score.title = title
        text_path = out_dir / f"{source.stem}_jianpu.txt"
        self.file_service.write_text(text_path, score_to_jianpu_text(score))
        svg_path = out_dir / f"{source.stem}_jianpu.svg"
        if ocr_image_path is not None:
            page_width, page_height = image_dimensions(ocr_image_path)
            self.renderer.render_score_page_svg(
                score,
                svg_path,
                page_width=page_width,
                page_height=page_height,
                title=title or score.title,
            )
        else:
            self.renderer.render_score_svg(score, svg_path, title=title or score.title)
        return ScorePipelineOutputs(
            input_path=source,
            musicxml_path=musicxml_path,
            jianpu_text_path=text_path,
            jianpu_svg_path=svg_path,
        )


class PipelineActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        settings: SettingsService | None = None,
        pipeline: FullPipelineAction | None = None,
        file_service: FileService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.settings = settings or SettingsService()
        self.pipeline = pipeline or FullPipelineAction()
        self.file_service = file_service or FileService()

    def run_pipeline(
        self,
        file: UploadFile,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> PipelineResponse:
        config = self.settings.load()
        file_id = self.uploads.save(file)
        input_path = self.uploads.get_path(file_id)
        if not input_path:
            raise HTTPException(500, "文件保存失败")

        output_dir = config.work_dir / "pipeline" / uuid.uuid4().hex[:12]
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = self.pipeline.execute(
            input_path,
            output_dir,
            config=config,
            target_key=target_key,
            start_measure_number=start_measure_number,
            title=title,
        )

        musicxml_id = self.uploads.register(outputs.musicxml_path)
        jianpu_id = self.uploads.register(outputs.jianpu_text_path)
        svg_id = self.uploads.register(outputs.jianpu_svg_path)
        jianpu_text = self.file_service.read_text(outputs.jianpu_text_path)
        return PipelineResponse(
            musicxml_file_id=musicxml_id,
            jianpu_text=jianpu_text,
            jianpu_file_id=jianpu_id,
            svg_file_id=svg_id,
        )


def _copy_musicxml_output(path: Path, output_dir: Path, stem: str) -> Path:
    suffix = path.suffix if path.suffix.lower() in {".musicxml", ".mxl", ".xml"} else ".musicxml"
    target = output_dir / f"{stem}{suffix}"
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    return target


def _is_ocr_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES

