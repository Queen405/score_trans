from __future__ import annotations

import asyncio
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from ...domain.musicxml import score_to_jianpu_text
from ...models.pipeline.schemas import PipelineResponse
from ...models.settings.config import ToolConfig
from ...models.tasks.entities import ProgressCallback, report_progress
from ...models.tasks.schemas import TaskSubmitResponse
from ...services.files.file_service import FileService
from ...services.files.image_info import image_dimensions
from ...services.files.upload_service import UploadService
from ...services.ocr.core import OCRProvider
from ...services.recognize.image_preprocessing import IMAGE_SUFFIXES
from ...services.render.render_service import RenderService
from ...services.settings.settings_service import SettingsService
from ..convert.actions import MusicXmlToJianpuAction
from ..recognize.actions import RecognizeScoreAction
from ..tasks.actions import TaskActions
from ..tasks.background import OMR_SEMAPHORE, run_sync_task, schedule_background_task


@dataclass(slots=True)
class ScorePipelineOutputs:
    input_path: Path
    musicxml_path: Path
    jianpu_text_path: Path
    jianpu_svg_path: Path
    ocr_measure_numbers: list[int]


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
        progress_callback: ProgressCallback | None = None,
    ) -> ScorePipelineOutputs:
        source = Path(input_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        report_progress(progress_callback, "omr", 10, "准备 OMR 识别")
        recognized = self.recognizer.execute(source, out_dir / "omr", config)
        report_progress(progress_callback, "omr", 45, "OMR 识别完成")
        musicxml_path = _copy_musicxml_output(Path(recognized), out_dir, source.stem)
        ocr_image_path = source if _is_ocr_image(source) else None
        report_progress(progress_callback, "convert", 55, "转换 MusicXML")
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            image_path=ocr_image_path,
            ocr_provider=ocr_provider,
        )
        if title:
            score.title = title
        report_progress(progress_callback, "convert", 72, "生成简谱文本")
        text_path = out_dir / f"{source.stem}_jianpu.txt"
        self.file_service.write_text(text_path, score_to_jianpu_text(score))
        svg_path = out_dir / f"{source.stem}_jianpu.svg"
        report_progress(progress_callback, "render", 82, "渲染简谱 SVG")
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
        ocr_measure_numbers = _extract_ocr_measure_numbers(score)
        report_progress(progress_callback, "render", 94, "渲染完成")
        return ScorePipelineOutputs(
            input_path=source,
            musicxml_path=musicxml_path,
            jianpu_text_path=text_path,
            jianpu_svg_path=svg_path,
            ocr_measure_numbers=ocr_measure_numbers,
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
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResponse:
        input_path = self.save_upload(file)
        return self.run_pipeline_from_path(
            input_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            title=title,
            progress_callback=progress_callback,
        )

    def save_upload(self, file: UploadFile) -> Path:
        file_id = self.uploads.save(file)
        input_path = self.uploads.get_path(file_id)
        if not input_path:
            raise FileNotFoundError("文件保存失败")
        return input_path

    async def submit_pipeline_task_by_file_id(
        self,
        app: Any,
        file_id: str,
        *,
        tasks: TaskActions,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> TaskSubmitResponse:
        input_path = self.uploads.get_path(file_id)
        if not input_path or not input_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_id}")
        task_id = tasks.create_task()

        def action(progress: ProgressCallback):
            return self.run_pipeline_from_path(
                input_path,
                target_key=target_key,
                start_measure_number=start_measure_number,
                title=title,
                progress_callback=progress,
            )

        schedule_background_task(
            app, task_id, run_sync_task(task_id, tasks, action, semaphore=OMR_SEMAPHORE)
        )
        return TaskSubmitResponse(task_id=task_id)

    async def submit_pipeline_task(
        self,
        app: Any,
        file: UploadFile,
        *,
        tasks: TaskActions,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
    ) -> TaskSubmitResponse:
        input_path = await asyncio.to_thread(self.save_upload, file)
        task_id = tasks.create_task()

        def action(progress: ProgressCallback):
            return self.run_pipeline_from_path(
                input_path,
                target_key=target_key,
                start_measure_number=start_measure_number,
                title=title,
                progress_callback=progress,
            )

        schedule_background_task(
            app, task_id, run_sync_task(task_id, tasks, action, semaphore=OMR_SEMAPHORE)
        )
        return TaskSubmitResponse(task_id=task_id)

    def run_pipeline_from_path(
        self,
        input_path: str | Path,
        *,
        target_key: str = "C",
        start_measure_number: int | None = None,
        title: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResponse:
        config = self.settings.load()

        report_progress(progress_callback, "pipeline", 5, "创建输出目录")
        output_dir = config.work_dir / "pipeline" / uuid.uuid4().hex[:12]
        output_dir.mkdir(parents=True, exist_ok=True)
        outputs = self.pipeline.execute(
            input_path,
            output_dir,
            config=config,
            target_key=target_key,
            start_measure_number=start_measure_number,
            title=title,
            progress_callback=progress_callback,
        )

        report_progress(progress_callback, "pipeline", 96, "注册输出文件")
        musicxml_id = self.uploads.register(outputs.musicxml_path)
        jianpu_id = self.uploads.register(outputs.jianpu_text_path)
        svg_id = self.uploads.register(outputs.jianpu_svg_path)
        jianpu_text = self.file_service.read_text(outputs.jianpu_text_path)
        return PipelineResponse(
            musicxml_file_id=musicxml_id,
            jianpu_text=jianpu_text,
            jianpu_file_id=jianpu_id,
            svg_file_id=svg_id,
            ocr_measure_numbers=outputs.ocr_measure_numbers,
        )


def _copy_musicxml_output(path: Path, output_dir: Path, stem: str) -> Path:
    suffix = (
        path.suffix
        if path.suffix.lower() in {".musicxml", ".mxl", ".xml"}
        else ".musicxml"
    )
    target = output_dir / f"{stem}{suffix}"
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    return target


def _extract_ocr_measure_numbers(score) -> list[int]:
    numbers = sorted(
        {
            int(block.text.strip())
            for block in getattr(score, "text_blocks", [])
            if getattr(block, "role", None) == "measure_number"
            and block.text.strip().isdigit()
        }
    )
    return numbers


def _is_ocr_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES
