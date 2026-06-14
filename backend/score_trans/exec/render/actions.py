from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import HTTPException

from ...domain.accidentals import score_with_accidental_mode
from ...domain.jianpu import normalize_jianpu_text
from ...models.common.types import AccidentalMode, MeasureNumberMode
from ...models.render.schemas import (
    FinalRenderRequest,
    FinalRenderResponse,
    NormalizeJianpuTextRequest,
    NormalizeJianpuTextResponse,
    PreservingLayoutRequest,
    PreservingLayoutResponse,
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
    RenderJianpuTextSvgRequest,
    RenderJianpuTextSvgResponse,
)
from ...models.score import JianpuScore, TextBlock
from ...services.files.image_info import image_dimensions
from ...services.files.upload_service import UploadService
from ...services.ocr.core import OCRProvider
from ...services.ocr.providers import create_configured_ocr_provider
from ...services.render.render_service import RenderService
from ..convert.actions import MusicXmlToJianpuAction


class RenderMusicXmlJianpuAction:
    def __init__(
        self,
        converter: MusicXmlToJianpuAction | None = None,
        render_service: RenderService | None = None,
    ) -> None:
        self.converter = converter or MusicXmlToJianpuAction()
        self.render_service = render_service or RenderService()

    def execute(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            start_measure_number=start_measure_number,
            title=title,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        return self.render_service.render_score_svg(
            score,
            output_path,
            title=title or score.title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def execute_page(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            start_measure_number=start_measure_number,
            title=title,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        return self.render_service.render_score_page_svg(
            score,
            output_path,
            page_width=page_width,
            page_height=page_height,
            title=title or score.title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def build_score(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        start_measure_number: int | None = None,
        title: str | None = None,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
    ) -> JianpuScore:
        score = self.converter.build_score(
            musicxml_path,
            target_key=target_key,
            start_measure_number=start_measure_number,
            image_path=image_path,
            ocr_provider=ocr_provider,
        )
        if title:
            score.title = title
        return score_with_accidental_mode(score, accidental_mode=accidental_mode)


class RenderJianpuTextAction:
    def __init__(self, render_service: RenderService | None = None) -> None:
        self.render_service = render_service or RenderService()

    def execute(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        title: str = "简谱",
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
    ) -> Path:
        return self.render_service.render_text_svg(
            input_path,
            output_path,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def execute_page(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        page_width: float,
        page_height: float,
        image_path: str | Path | None = None,
        ocr_provider: OCRProvider | None = None,
        text_blocks: list[TextBlock] | None = None,
        title: str = "简谱",
        start_measure_number: int | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
    ) -> Path:
        blocks = text_blocks
        if blocks is None and image_path is not None:
            provider = ocr_provider or create_configured_ocr_provider()
            blocks = provider.recognize(Path(image_path))
        return self.render_service.render_text_page_svg(
            input_path,
            output_path,
            page_width=page_width,
            page_height=page_height,
            title=title,
            text_blocks=blocks or [],
            start_measure_number=start_measure_number,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )


class RenderActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        musicxml_renderer: RenderMusicXmlJianpuAction | None = None,
        text_renderer: RenderJianpuTextAction | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.musicxml_renderer = musicxml_renderer or RenderMusicXmlJianpuAction()
        self.text_renderer = text_renderer or RenderJianpuTextAction()

    def render_jianpu_svg(self, req: RenderJianpuSvgRequest) -> RenderJianpuSvgResponse:
        path = self.uploads.get_path(req.musicxml_file_id)
        if not path or not path.exists():
            raise HTTPException(404, f"文件不存在：{req.musicxml_file_id}")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")
            page_width, page_height = image_dimensions(image_path)
            self.musicxml_renderer.execute_page(
                path,
                svg_path,
                page_width=page_width,
                page_height=page_height,
                target_key=req.target_key,
                accidental_mode=req.accidental_mode,
                start_measure_number=req.start_measure_number,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                image_path=image_path,
                title=req.title,
            )
        else:
            self.musicxml_renderer.execute(
                path,
                svg_path,
                target_key=req.target_key,
                accidental_mode=req.accidental_mode,
                start_measure_number=req.start_measure_number,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                title=req.title,
            )
        return RenderJianpuSvgResponse(svg_file_id=self.uploads.register(svg_path))

    def render_jianpu_text_svg(self, req: RenderJianpuTextSvgRequest) -> RenderJianpuTextSvgResponse:
        normalized_text: str | None = None
        if req.jianpu_text:
            try:
                normalized_text = normalize_jianpu_text(req.jianpu_text, title=req.title)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            input_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.txt"
            input_path.write_text(normalized_text, encoding="utf-8")
        elif req.jianpu_file_id:
            input_path = self.uploads.get_path(req.jianpu_file_id)
            if not input_path or not input_path.exists():
                raise HTTPException(404, f"文件不存在：{req.jianpu_file_id}")
        else:
            raise HTTPException(400, "必须提供 jianpu_text 或 jianpu_file_id")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        ocr_blocks: list[TextBlock] | None = None
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")
            page_width, page_height = image_dimensions(image_path)
            ocr_blocks = (
                _parse_ocr_text(req.ocr_text)
                if req.ocr_text
                else create_configured_ocr_provider().recognize(image_path)
            )
            self.text_renderer.execute_page(
                input_path,
                svg_path,
                page_width=page_width,
                page_height=page_height,
                image_path=image_path,
                text_blocks=ocr_blocks if req.include_ocr_text else [],
                title=req.title,
                start_measure_number=req.start_measure_number,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
            )
        else:
            self.text_renderer.execute(
                input_path,
                svg_path,
                title=req.title,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
            )

        return RenderJianpuTextSvgResponse(
            svg_file_id=self.uploads.register(svg_path),
            ocr_text=_serialize_ocr_text(ocr_blocks) if ocr_blocks is not None else None,
            jianpu_text=req.jianpu_text,
        )

    def normalize_jianpu_text(self, req: NormalizeJianpuTextRequest) -> NormalizeJianpuTextResponse:
        try:
            return NormalizeJianpuTextResponse(jianpu_text=normalize_jianpu_text(req.jianpu_text, title=req.title))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    def render_preserving_layout(self, req: PreservingLayoutRequest) -> PreservingLayoutResponse:
        response = self._render_final_page(req, require_page_image=True)
        return PreservingLayoutResponse(**response.model_dump())

    def render_final_output(self, req: FinalRenderRequest) -> FinalRenderResponse:
        return self._render_final_page(req, require_page_image=False)

    def _render_final_page(
        self,
        req: FinalRenderRequest | PreservingLayoutRequest,
        *,
        require_page_image: bool,
    ) -> FinalRenderResponse:
        musicxml_path = self.uploads.get_path(req.musicxml_file_id)
        if not musicxml_path or not musicxml_path.exists():
            raise HTTPException(404, f"MusicXML 文件不存在：{req.musicxml_file_id}")

        image_path = None
        page_width = 1600.0
        page_height = 1200.0
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")
            page_width, page_height = image_dimensions(image_path)
        elif require_page_image:
            raise HTTPException(400, "必须提供 page_image_file_id")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        self.musicxml_renderer.execute_page(
            musicxml_path,
            svg_path,
            page_width=page_width,
            page_height=page_height,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            start_measure_number=req.start_measure_number,
            show_measure_numbers=_request_show_measure_numbers(req),
            measure_number_mode=_request_measure_number_mode(req),
            image_path=image_path,
            title=req.title,
        )
        return FinalRenderResponse(
            svg_file_id=self.uploads.register(svg_path),
            page_width=page_width,
            page_height=page_height,
        )


def _parse_ocr_text(payload: str) -> list[TextBlock]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"OCR 数据不是有效 JSON：{exc.msg}") from exc
    if not isinstance(raw, list):
        raise HTTPException(400, "OCR 数据必须是数组")

    blocks: list[TextBlock] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        bbox_raw = item.get("bbox")
        bbox = None
        if isinstance(bbox_raw, list | tuple) and len(bbox_raw) == 4:
            try:
                bbox = tuple(float(v) for v in bbox_raw)
            except (TypeError, ValueError):
                bbox = None
        role = item.get("role") or "other"
        if role not in {"title", "instrument", "lyric", "expression", "footer", "measure_number", "other"}:
            role = "other"
        font_size = item.get("fontSize", item.get("font_size"))
        try:
            font_size = float(font_size) if font_size is not None else None
        except (TypeError, ValueError):
            font_size = None
        blocks.append(TextBlock(text=text, bbox=bbox, role=role, font_size=font_size))
    return blocks


def _serialize_ocr_text(blocks: list[TextBlock]) -> str:
    return json.dumps(
        [
            {
                "id": f"ocr-{index}",
                "text": block.text,
                "bbox": list(block.bbox) if block.bbox is not None else None,
                "role": block.role,
                "fontSize": block.font_size,
            }
            for index, block in enumerate(blocks)
            if block.text.strip()
        ],
        ensure_ascii=False,
    )


def _request_measure_number_mode(req) -> MeasureNumberMode:
    if getattr(req, "show_measure_numbers", None) is False:
        return "none"
    return getattr(req, "measure_number_mode", "all")


def _show_measure_numbers(mode: MeasureNumberMode) -> bool:
    return mode != "none"


def _request_show_measure_numbers(req) -> bool:
    return _show_measure_numbers(_request_measure_number_mode(req))

