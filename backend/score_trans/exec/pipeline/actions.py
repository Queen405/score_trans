from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from ...domain.write.jianpu_text import scores_to_jianpu_document
from ...domain.accidentals import score_with_accidental_mode
from ...domain.text_attachments import build_source_text_attachments
from ...models.common.types import (
    AccidentalMode,
    IMAGE_SUFFIXES,
    InstrumentProfile,
    MeasureNumberMode,
)
from ...models.pipeline.schemas import PipelineResponse
from ...models.render.schemas import RenderedSvgPage
from ...models.provenance.schemas import SourceMap, SourceTextAttachment, TextAnchor
from ...models.score import TextBlock
from ...models.settings.config import ToolConfig
from ...models.tasks.entities import ProgressCallback, report_progress
from ...models.tasks.schemas import TaskSubmitResponse
from ...services.files.file_service import FileService
from ...services.files.image_info import image_dimensions
from ...services.files.upload_service import UploadService
from ...services.ocr.core import OCRProvider
from ...services.overlay.overlay_service import OverlayService
from ...services.render.render_service import RenderService
from ...services.render.render_map import write_render_map
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
    jianpu_svg_paths: list[Path]
    ocr_measure_numbers: list[int]
    ocr_text: str = ""
    overlay_path: Path | None = None
    source_map_path: Path | None = None
    overlay_svg_path: Path | None = None
    text_anchors: list[TextAnchor] | None = None
    text_attachments: list[SourceTextAttachment] | None = None
    text_hash: str = ""

    @property
    def jianpu_svg_path(self) -> Path:
        return self.jianpu_svg_paths[0]


class FullPipelineAction:
    def __init__(
        self,
        recognizer: RecognizeScoreAction | None = None,
        converter: MusicXmlToJianpuAction | None = None,
        renderer: RenderService | None = None,
        file_service: FileService | None = None,
        overlay_service: OverlayService | None = None,
    ) -> None:
        self.recognizer = recognizer or RecognizeScoreAction()
        self.converter = converter or MusicXmlToJianpuAction()
        self.renderer = renderer or RenderService()
        self.file_service = file_service or FileService()
        self.overlay_service = overlay_service or OverlayService()

    def execute(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        *,
        config: ToolConfig,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile = "general",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
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
        overlay_path, source_map_path = self.overlay_service.find_native_overlay(
            out_dir / "omr"
        )
        overlay_svg_path = (
            _generate_overlay(self.overlay_service, out_dir / "omr")
            if overlay_path is None
            else None
        )
        report_progress(progress_callback, "convert", 55, "转换 MusicXML")
        scores = self.converter.build_scores(
            musicxml_path,
            target_key=target_key,
            instrument_profile=instrument_profile,
            start_measure_number=start_measure_number,
            image_path=ocr_image_path,
            ocr_provider=ocr_provider,
        )
        if title:
            for score in scores:
                score.title = title
        report_progress(progress_callback, "convert", 72, "生成简谱文本")
        text_path = out_dir / f"{source.stem}_jianpu.txt"
        document = scores_to_jianpu_document(scores, accidental_mode=accidental_mode)
        self.file_service.write_text(text_path, document.text)
        render_scores = [
            score_with_accidental_mode(score, accidental_mode=accidental_mode)
            for score in scores
        ]
        svg_path = out_dir / f"{source.stem}_jianpu.svg"
        report_progress(progress_callback, "render", 82, "渲染简谱 SVG")
        rendered_pages = self.renderer.render_scores_a4_svg_pages(
            render_scores,
            svg_path,
            title=title or (render_scores[0].title if render_scores else "简谱"),
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )
        svg_paths = _rendered_page_paths(rendered_pages)
        first_score = render_scores[0] if render_scores else None
        ocr_measure_numbers = (
            _extract_ocr_measure_numbers(first_score) if first_score else []
        )
        source_map = _load_source_map(source_map_path)
        source_image_size = _source_image_size(source)
        ocr_blocks = _visible_ocr_blocks(first_score.text_blocks) if first_score else []
        text_attachments = (
            build_source_text_attachments(
                ocr_blocks,
                first_score,
                source_map,
                image_size=source_image_size,
            )
            if first_score
            else []
        )
        ocr_text = _serialize_text_attachments(text_attachments)
        report_progress(progress_callback, "render", 94, "渲染完成")
        return ScorePipelineOutputs(
            input_path=source,
            musicxml_path=musicxml_path,
            jianpu_text_path=text_path,
            jianpu_svg_paths=svg_paths,
            ocr_measure_numbers=ocr_measure_numbers,
            ocr_text=ocr_text,
            overlay_path=overlay_path,
            source_map_path=source_map_path,
            overlay_svg_path=overlay_svg_path,
            text_anchors=document.anchors,
            text_attachments=text_attachments,
            text_hash=document.text_hash,
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
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile = "general",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        title: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResponse:
        input_path = self.save_upload(file)
        return self.run_pipeline_from_path(
            input_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            start_measure_number=start_measure_number,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
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
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile = "general",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
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
                accidental_mode=accidental_mode,
                instrument_profile=instrument_profile,
                start_measure_number=start_measure_number,
                show_measure_numbers=show_measure_numbers,
                measure_number_mode=measure_number_mode,
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
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile = "general",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        title: str | None = None,
    ) -> TaskSubmitResponse:
        input_path = await asyncio.to_thread(self.save_upload, file)
        task_id = tasks.create_task()

        def action(progress: ProgressCallback):
            return self.run_pipeline_from_path(
                input_path,
                target_key=target_key,
                accidental_mode=accidental_mode,
                instrument_profile=instrument_profile,
                start_measure_number=start_measure_number,
                show_measure_numbers=show_measure_numbers,
                measure_number_mode=measure_number_mode,
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
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile = "general",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
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
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            start_measure_number=start_measure_number,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            title=title,
            progress_callback=progress_callback,
        )

        report_progress(progress_callback, "pipeline", 96, "注册输出文件")
        musicxml_id = self.uploads.register(outputs.musicxml_path)
        jianpu_id = self.uploads.register(outputs.jianpu_text_path)
        render_pages = [
            RenderedSvgPage(
                svg_file_id=self.uploads.register(path),
                page_index=index,
                page_width=1240,
                page_height=1754,
                ocr_text=outputs.ocr_text if index == 0 else "",
                render_map_file_id=(
                    self.uploads.register(render_map_path)
                    if (render_map_path := write_render_map(path, index))
                    else None
                ),
            )
            for index, path in enumerate(outputs.jianpu_svg_paths)
        ]
        jianpu_text = self.file_service.read_text(outputs.jianpu_text_path)
        overlay_svg_file_id = (
            self.uploads.register(outputs.overlay_svg_path)
            if outputs.overlay_svg_path
            else None
        )
        overlay_file_id = (
            self.uploads.register(outputs.overlay_path)
            if outputs.overlay_path
            else None
        )
        source_map_file_id = (
            self.uploads.register(outputs.source_map_path)
            if outputs.source_map_path
            else None
        )
        return PipelineResponse(
            musicxml_file_id=musicxml_id,
            jianpu_text=jianpu_text,
            jianpu_file_id=jianpu_id,
            svg_file_id=render_pages[0].svg_file_id,
            render_pages=render_pages,
            ocr_measure_numbers=outputs.ocr_measure_numbers,
            ocr_text=outputs.ocr_text,
            overlay_file_id=overlay_file_id,
            source_map_file_id=source_map_file_id,
            overlay_svg_file_id=overlay_svg_file_id,
            text_anchors=outputs.text_anchors or [],
            text_attachments=outputs.text_attachments or [],
            text_hash=outputs.text_hash,
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


def _visible_ocr_blocks(blocks: list[TextBlock]) -> list[TextBlock]:
    return [
        block
        for block in blocks
        if block.text.strip()
        and block.role != "measure_number"
        and (block.bbox is not None or block.confidence is not None)
    ]


def _serialize_text_attachments(items: list[SourceTextAttachment]) -> str:
    if not items:
        return ""
    return json.dumps(
        [
            {
                "id": item.id,
                "text": item.text,
                "bbox": (
                    [
                        item.source_bbox.x,
                        item.source_bbox.y,
                        item.source_bbox.x + item.source_bbox.width,
                        item.source_bbox.y + item.source_bbox.height,
                    ]
                    if item.source_bbox is not None
                    else None
                ),
                "role": item.role,
                "fontSize": item.font_size,
                "confidence": item.ocr_confidence,
                "anchor": item.anchor.model_dump(),
            }
            for item in items
        ],
        ensure_ascii=False,
    )


def _load_source_map(path: Path | None) -> SourceMap | None:
    if path is None:
        return None
    try:
        return SourceMap.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _source_image_size(path: Path) -> tuple[int, int] | None:
    if not _is_ocr_image(path):
        return None
    try:
        width, height = image_dimensions(path)
    except OSError:
        return None
    return int(width), int(height)


def _rendered_page_paths(rendered_pages) -> list[Path]:
    return [
        Path(page.path) if hasattr(page, "path") else Path(page)
        for page in rendered_pages
    ]


def _is_ocr_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def _generate_overlay(overlay_service: OverlayService, omr_dir: Path) -> Path | None:
    try:
        paths = overlay_service.generate_overlay_svgs(omr_dir)
    except Exception:
        return None
    return paths[0] if paths else None
