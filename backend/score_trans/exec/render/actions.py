from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from ...domain.accidentals import score_with_accidental_mode
from ...domain.jianpu import (
    normalize_jianpu_text,
)
from ...domain.parse.jianpu_text import parse_jianpu_parts
from ...domain.provenance import apply_text_anchors_to_parts
from ...domain.text_placement import place_source_text_attachments
from ...models.common.errors import (
    CodedValidationError,
    JianpuValidationError,
    RenderError,
)
from ...models.common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
)
from ...models.provenance.schemas import RenderedTextBlock, TextAnchor
from ...models.render.schemas import (
    BatchRenderPageRequest,
    BatchRenderRequest,
    BatchRenderResponse,
    FinalRenderRequest,
    FinalRenderResponse,
    NormalizeJianpuTextRequest,
    NormalizeJianpuTextResponse,
    PreservingLayoutRequest,
    PreservingLayoutResponse,
    RenderedSvgPage,
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
    RenderJianpuTextSvgRequest,
    RenderJianpuTextSvgResponse,
    RenderPageMeasureRange,
)
from ...models.score import JianpuScore, TextBlock
from ...services.files.image_info import image_dimensions
from ...services.files.upload_service import UploadService
from ...services.ocr.providers import create_configured_ocr_provider
from ...services.render import A4MeasureRange, RenderedA4FilePage
from ...services.render.render_service import PublicationRenderService
from ..convert.actions import MusicXmlToJianpuAction


@dataclass(slots=True)
class _SourcePageRange:
    source_page_index: int
    start_measure_number: int | None
    end_measure_number: int | None


class RenderMusicXmlJianpuAction:
    def __init__(
        self,
        converter: MusicXmlToJianpuAction | None = None,
        render_service: PublicationRenderService | None = None,
    ) -> None:
        self.converter = converter or MusicXmlToJianpuAction()
        self.render_service = render_service or PublicationRenderService()

    def execute(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        initial_measure_number: int = 1,
        title: str | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            title=title,
        )
        return self.render_service.render_score_svg(
            score,
            output_path,
            title=title or score.title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
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
        instrument_profile: InstrumentProfile | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        initial_measure_number: int = 1,
        title: str | None = None,
    ) -> Path:
        score = self.build_score(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            title=title,
        )
        return self.render_service.render_score_page_svg(
            score,
            output_path,
            page_width=page_width,
            page_height=page_height,
            title=title or score.title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )

    def execute_a4_pages(
        self,
        musicxml_path: str | Path,
        output_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        initial_measure_number: int = 1,
        title: str | None = None,
    ) -> list[RenderedA4FilePage]:
        scores = self.build_scores(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            title=title,
        )
        _validate_multi_part_measure_counts(scores)
        first_score = scores[0] if scores else JianpuScore()
        return self.render_service.render_scores_a4_svg_pages(
            scores,
            output_path,
            title=title or first_score.title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
        )

    def build_score(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        title: str | None = None,
    ) -> JianpuScore:
        scores = self.build_scores(
            musicxml_path,
            target_key=target_key,
            accidental_mode=accidental_mode,
            instrument_profile=instrument_profile,
            title=title,
        )
        return scores[0] if scores else JianpuScore()

    def build_scores(
        self,
        musicxml_path: str | Path,
        *,
        target_key: str = "C",
        accidental_mode: AccidentalMode = "auto",
        instrument_profile: InstrumentProfile | None = None,
        title: str | None = None,
    ) -> list[JianpuScore]:
        scores = self.converter.build_scores(
            musicxml_path,
            target_key=target_key,
            instrument_profile=instrument_profile,
        )
        if title:
            for score in scores:
                score.title = title
        return [
            score_with_accidental_mode(score, accidental_mode=accidental_mode)
            for score in scores
        ]


class RenderJianpuTextAction:
    def __init__(self, render_service: PublicationRenderService | None = None) -> None:
        self.render_service = render_service or PublicationRenderService()

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
        title: str = "简谱",
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
    ) -> Path:
        return self.render_service.render_text_page_svg(
            input_path,
            output_path,
            page_width=page_width,
            page_height=page_height,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
        )

    def execute_a4_pages(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        title: str = "简谱",
        show_measure_numbers: bool = True,
        measure_number_mode: MeasureNumberMode = "all",
        initial_measure_number: int = 1,
        text_anchors: list[TextAnchor] | None = None,
    ) -> list[RenderedA4FilePage]:
        text = Path(input_path).read_text(encoding="utf-8")
        parts = parse_jianpu_parts(text, title=title)
        scores = [part.score for part in parts]
        _validate_multi_part_measure_counts(scores)
        if text_anchors:
            apply_text_anchors_to_parts(parts, text_anchors)
        return self.render_service.render_scores_a4_svg_pages(
            scores,
            output_path,
            title=title,
            show_measure_numbers=show_measure_numbers,
            measure_number_mode=measure_number_mode,
            initial_measure_number=initial_measure_number,
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
            raise FileNotFoundError(f"文件不存在：{req.musicxml_file_id}")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        paths = self.musicxml_renderer.execute_a4_pages(
            path,
            svg_path,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            instrument_profile=req.instrument_profile,
            show_measure_numbers=_request_show_measure_numbers(req),
            measure_number_mode=_request_measure_number_mode(req),
            initial_measure_number=req.initial_measure_number,
            title=req.title,
        )
        pages = self._register_rendered_pages(paths)
        return RenderJianpuSvgResponse(
            svg_file_id=pages[0].svg_file_id,
            pages=pages,
        )

    def render_jianpu_text_svg(
        self, req: RenderJianpuTextSvgRequest
    ) -> RenderJianpuTextSvgResponse:
        normalized_text: str | None = None
        if req.jianpu_text:
            normalized_text = (
                req.jianpu_text
                if req.text_anchors
                else normalize_jianpu_text(req.jianpu_text, title=req.title)
            )
            input_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.txt"
            input_path.write_text(normalized_text, encoding="utf-8")
        elif req.jianpu_file_id:
            input_path = self.uploads.get_path(req.jianpu_file_id)
            if not input_path or not input_path.exists():
                raise FileNotFoundError(f"文件不存在：{req.jianpu_file_id}")
        else:
            raise ValueError("必须提供 jianpu_text 或 jianpu_file_id")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        ocr_blocks: list[TextBlock] | None = None
        anchor_options = {"text_anchors": req.text_anchors} if req.text_anchors else {}
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"页面图片不存在：{req.page_image_file_id}")
            if req.ocr_text:
                ocr_blocks = _parse_ocr_text(req.ocr_text)
            elif req.include_ocr_text:
                ocr_blocks = create_configured_ocr_provider().recognize(image_path)
            paths = self.text_renderer.execute_a4_pages(
                input_path,
                svg_path,
                title=req.title,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                initial_measure_number=req.initial_measure_number,
                **anchor_options,
            )
        else:
            paths = self.text_renderer.execute_a4_pages(
                input_path,
                svg_path,
                title=req.title,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                initial_measure_number=req.initial_measure_number,
                **anchor_options,
            )
        pages = self._register_rendered_pages(paths)

        return RenderJianpuTextSvgResponse(
            svg_file_id=pages[0].svg_file_id,
            pages=pages,
            ocr_text=_serialize_ocr_text(ocr_blocks)
            if ocr_blocks is not None
            else None,
            jianpu_text=req.jianpu_text,
        )

    def normalize_jianpu_text(
        self, req: NormalizeJianpuTextRequest
    ) -> NormalizeJianpuTextResponse:
        return NormalizeJianpuTextResponse(
            jianpu_text=normalize_jianpu_text(req.jianpu_text, title=req.title)
        )

    def render_preserving_layout(
        self, req: PreservingLayoutRequest
    ) -> PreservingLayoutResponse:
        response = self._render_preserving_page(req, require_page_image=True)
        return PreservingLayoutResponse(**response.model_dump())

    def render_final_output(self, req: FinalRenderRequest) -> FinalRenderResponse:
        return self._render_final_a4(req)

    def render_batch_a4(self, req: BatchRenderRequest) -> BatchRenderResponse:
        if not req.pages:
            raise ValueError("至少需要一个待渲染页面")
        page_scores_list: list[list[JianpuScore]] = []
        for index, page in enumerate(req.pages):
            try:
                page_scores = self._build_batch_page_scores(req, page)
            except JianpuValidationError as exc:
                page_label = f"第 {index + 1} 页"
                if page.input_file_name:
                    page_label = f"{page_label}（{page.input_file_name}）"
                raise JianpuValidationError(f"{page_label}：{exc}") from exc
            except CodedValidationError:
                raise
            except ValueError as exc:
                page_label = f"第 {index + 1} 页"
                if page.input_file_name:
                    page_label = f"{page_label}（{page.input_file_name}）"
                raise ValueError(f"{page_label}：{exc}") from exc
            for score in page_scores:
                _tag_score_source_page(score, index)
            page_scores_list.append(page_scores)

        has_multi_part = any(len(scores) > 1 for scores in page_scores_list)

        if not has_multi_part:
            scores = [s for page_scores in page_scores_list for s in page_scores]
            _renumber_scores_continuously(
                scores, initial_measure_number=req.initial_measure_number
            )
            return self._render_batch_flat(req, scores)

        return self._render_batch_multi_part(req, page_scores_list)

    def _render_batch_flat(
        self,
        req: BatchRenderRequest,
        scores: list[JianpuScore],
    ) -> BatchRenderResponse:
        source_ranges = self._batch_source_ranges(req, scores)
        layout_pages = self.text_renderer.render_service.build_scores_a4_svg_pages(
            scores,
            title=req.title,
            show_measure_numbers=_request_show_measure_numbers(req),
            measure_number_mode=_request_measure_number_mode(req),
            initial_measure_number=None,
        )
        measure_ranges_by_page = [
            _page_measure_ranges(page.measure_ranges, source_ranges)
            for page in layout_pages
        ]
        legacy_page_ocr_texts = _resolved_render_page_ocr_texts(
            req,
            measure_ranges_by_page,
        )
        placement = place_source_text_attachments(
            [list(page.text_attachments) for page in (req.source_pages or req.pages)],
            [page.svg for page in layout_pages],
            measure_ranges_by_page,
        )
        page_ocr_texts = _merge_rendered_and_legacy_ocr_texts(
            legacy_page_ocr_texts,
            placement.rendered_blocks_by_page,
            len(layout_pages),
        )
        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        rendered_pages = (
            self.text_renderer.render_service.render_scores_a4_svg_page_results(
                scores,
                svg_path,
                title=req.title,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                initial_measure_number=None,
            )
        )
        pages = self._register_rendered_page_results(
            rendered_pages,
            page_ocr_texts,
            measure_ranges_by_page,
            placement.rendered_blocks_by_page,
        )
        return BatchRenderResponse(
            svg_file_id=pages[0].svg_file_id,
            pages=pages,
            page_width=pages[0].page_width,
            page_height=pages[0].page_height,
        )

    def _render_batch_multi_part(
        self,
        req: BatchRenderRequest,
        page_scores_list: list[list[JianpuScore]],
    ) -> BatchRenderResponse:
        current_measure: int | None = req.initial_measure_number
        for page_scores in page_scores_list:
            if current_measure is None:
                first_score = page_scores[0] if page_scores else None
                current_measure = (
                    _first_measure_number(first_score)
                    if first_score
                    else req.initial_measure_number
                )
            max_measure_count = 0
            for score in page_scores:
                count = sum(getattr(m, "repeat_count", 1) for m in score.measures)
                max_measure_count = max(max_measure_count, count)
            for score in page_scores:
                _renumber_score(score, current_measure or 1)
            current_measure = (current_measure or 1) + max_measure_count

        all_scores = [s for page_scores in page_scores_list for s in page_scores]
        source_ranges = self._batch_source_ranges(req, all_scores)
        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        all_rendered_file_pages: list[RenderedA4FilePage] = []
        all_measure_ranges: list[list[RenderPageMeasureRange]] = []
        all_page_ocr_texts: dict[int, str] = {}
        all_rendered_blocks: dict[int, list[RenderedTextBlock]] = {}
        source_pages = req.source_pages or req.pages
        page_offset = 0
        for page_idx, page_scores in enumerate(page_scores_list):
            layout_pages = self.text_renderer.render_service.build_scores_a4_svg_pages(
                page_scores,
                title=req.title,
                show_measure_numbers=_request_show_measure_numbers(req),
                measure_number_mode=_request_measure_number_mode(req),
                initial_measure_number=None,
            )
            page_source_ranges = (
                [
                    r
                    for r in source_ranges
                    if r.source_page_index
                    == page_scores[0].measures[0].source_page_index
                ]
                if page_scores and page_scores[0].measures
                else []
            )
            measure_ranges_by_page = [
                _page_measure_ranges(page.measure_ranges, page_source_ranges)
                for page in layout_pages
            ]
            all_measure_ranges.extend(measure_ranges_by_page)
            legacy_page_ocr_texts = _resolved_render_page_ocr_texts(
                req,
                measure_ranges_by_page,
                page_offset=page_offset,
                source_page_indices=[page_idx],
            )
            current_attachments = (
                [list(source_pages[page_idx].text_attachments)]
                if page_idx < len(source_pages)
                else []
            )
            placement = place_source_text_attachments(
                current_attachments,
                [page.svg for page in layout_pages],
                measure_ranges_by_page,
            )
            page_ocr_texts = _merge_rendered_and_legacy_ocr_texts(
                legacy_page_ocr_texts,
                placement.rendered_blocks_by_page,
                len(layout_pages),
            )
            for pi, text in page_ocr_texts.items():
                all_page_ocr_texts[page_offset + pi] = text
            for pi, blocks in placement.rendered_blocks_by_page.items():
                all_rendered_blocks.setdefault(page_offset + pi, []).extend(blocks)
            page_svg_path = (
                svg_path.with_stem(f"{svg_path.stem}_p{page_offset + 1}")
                if page_offset > 0
                else svg_path
            )
            rendered_pages = (
                self.text_renderer.render_service.render_scores_a4_svg_page_results(
                    page_scores,
                    page_svg_path,
                    title=req.title,
                    show_measure_numbers=_request_show_measure_numbers(req),
                    measure_number_mode=_request_measure_number_mode(req),
                    initial_measure_number=None,
                )
            )
            all_rendered_file_pages.extend(rendered_pages)
            page_offset += len(rendered_pages)

        pages = self._register_rendered_page_results(
            all_rendered_file_pages,
            all_page_ocr_texts,
            all_measure_ranges,
            all_rendered_blocks,
        )
        return BatchRenderResponse(
            svg_file_id=pages[0].svg_file_id,
            pages=pages,
            page_width=pages[0].page_width,
            page_height=pages[0].page_height,
        )

    def _batch_source_ranges(
        self,
        req: BatchRenderRequest,
        rendered_scores: list[JianpuScore],
    ) -> list[_SourcePageRange]:
        source_pages = req.source_pages or req.pages
        if source_pages == req.pages:
            return _source_ranges_for_scores(rendered_scores)
        source_scores: list[JianpuScore] = []
        for index, page in enumerate(source_pages):
            score = self._build_batch_page_score(req, page)
            _tag_score_source_page(score, index)
            source_scores.append(score)
        _renumber_scores_continuously(
            source_scores, initial_measure_number=req.initial_measure_number
        )
        return _source_ranges_for_scores(source_scores)

    def _render_final_a4(self, req: FinalRenderRequest) -> FinalRenderResponse:
        musicxml_path = self.uploads.get_path(req.musicxml_file_id)
        if not musicxml_path or not musicxml_path.exists():
            raise FileNotFoundError(f"MusicXML 文件不存在：{req.musicxml_file_id}")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        paths = self.musicxml_renderer.execute_a4_pages(
            musicxml_path,
            svg_path,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            instrument_profile=req.instrument_profile,
            show_measure_numbers=_request_show_measure_numbers(req),
            measure_number_mode=_request_measure_number_mode(req),
            initial_measure_number=req.initial_measure_number,
            title=req.title,
        )
        pages = self._register_rendered_pages(paths)
        return FinalRenderResponse(
            svg_file_id=pages[0].svg_file_id,
            pages=pages,
            page_width=pages[0].page_width,
            page_height=pages[0].page_height,
        )

    def _render_preserving_page(
        self,
        req: FinalRenderRequest | PreservingLayoutRequest,
        *,
        require_page_image: bool,
    ) -> FinalRenderResponse:
        musicxml_path = self.uploads.get_path(req.musicxml_file_id)
        if not musicxml_path or not musicxml_path.exists():
            raise FileNotFoundError(f"MusicXML 文件不存在：{req.musicxml_file_id}")

        image_path = None
        page_width = 1600.0
        page_height = 1200.0
        if req.page_image_file_id:
            image_path = self.uploads.get_path(req.page_image_file_id)
            if not image_path or not image_path.exists():
                raise FileNotFoundError(f"页面图片不存在：{req.page_image_file_id}")
            page_width, page_height = image_dimensions(image_path)
        elif require_page_image:
            raise ValueError("必须提供 page_image_file_id")

        svg_path = self.uploads.base_dir / f"{uuid.uuid4().hex[:12]}.svg"
        self.musicxml_renderer.execute_page(
            musicxml_path,
            svg_path,
            page_width=page_width,
            page_height=page_height,
            target_key=req.target_key,
            accidental_mode=req.accidental_mode,
            instrument_profile=req.instrument_profile,
            show_measure_numbers=_request_show_measure_numbers(req),
            measure_number_mode=_request_measure_number_mode(req),
            title=req.title,
        )
        return FinalRenderResponse(
            svg_file_id=self.uploads.register(svg_path),
            pages=[],
            page_width=page_width,
            page_height=page_height,
        )

    def _build_batch_page_score(
        self,
        req: BatchRenderRequest,
        page: BatchRenderPageRequest,
    ) -> JianpuScore:
        scores = self._build_batch_page_scores(req, page)
        return scores[0] if scores else JianpuScore()

    def _build_batch_page_scores(
        self,
        req: BatchRenderRequest,
        page: BatchRenderPageRequest,
    ) -> list[JianpuScore]:
        if page.musicxml_file_id:
            musicxml_path = self.uploads.get_path(page.musicxml_file_id)
            if not musicxml_path or not musicxml_path.exists():
                raise FileNotFoundError(f"MusicXML 文件不存在：{page.musicxml_file_id}")
            scores = self.musicxml_renderer.build_scores(
                musicxml_path,
                target_key=req.target_key,
                instrument_profile=req.instrument_profile,
                title=page.title or req.title,
            )
            rendered_scores = [
                score_with_accidental_mode(s, accidental_mode=req.accidental_mode)
                for s in scores
            ]
            _validate_multi_part_measure_counts(rendered_scores)
            return rendered_scores
        if page.jianpu_text or page.jianpu_file_id:
            if page.jianpu_text:
                text = page.jianpu_text
            else:
                input_path = self.uploads.get_path(page.jianpu_file_id or "")
                if not input_path or not input_path.exists():
                    raise FileNotFoundError(f"文件不存在：{page.jianpu_file_id}")
                text = input_path.read_text(encoding="utf-8")
            parts = parse_jianpu_parts(text, title=page.title or req.title)
            if page.text_anchors:
                apply_text_anchors_to_parts(parts, page.text_anchors)
            scores = [part.score for part in parts]
            scores = [
                score_with_accidental_mode(s, accidental_mode=req.accidental_mode)
                for s in scores
            ]
            _validate_multi_part_measure_counts(scores)
            return scores
        raise ValueError(
            "每个页面必须提供 musicxml_file_id、jianpu_text 或 jianpu_file_id"
        )

    def _register_rendered_pages(
        self, rendered_pages: list[RenderedA4FilePage]
    ) -> list[RenderedSvgPage]:
        if not rendered_pages:
            raise RenderError("渲染未生成任何 SVG 页面")
        pages: list[RenderedSvgPage] = []
        for index, rendered_page in enumerate(rendered_pages):
            path = rendered_page.path
            render_map_path = rendered_page.render_map_path
            pages.append(
                RenderedSvgPage(
                    svg_file_id=self.uploads.register(path),
                    page_index=index,
                    page_width=1240,
                    page_height=1754,
                    render_map_file_id=(
                        self.uploads.register(render_map_path)
                        if render_map_path is not None
                        else None
                    ),
                    note_index_start=rendered_page.note_index_start,
                    note_index_end=rendered_page.note_index_end,
                )
            )
        return pages

    def _register_rendered_page_results(
        self,
        rendered_pages,
        page_ocr_texts: dict[int, str],
        measure_ranges_by_page: list[list[RenderPageMeasureRange]],
        rendered_text_blocks: dict[int, list[RenderedTextBlock]] | None = None,
    ) -> list[RenderedSvgPage]:
        if not rendered_pages:
            raise RenderError("渲染未生成任何 SVG 页面")
        pages: list[RenderedSvgPage] = []
        for index, rendered_page in enumerate(rendered_pages):
            render_map_path = rendered_page.render_map_path
            pages.append(
                RenderedSvgPage(
                    svg_file_id=self.uploads.register(rendered_page.path),
                    page_index=index,
                    page_width=1240,
                    page_height=1754,
                    measure_ranges=measure_ranges_by_page[index]
                    if index < len(measure_ranges_by_page)
                    else [],
                    ocr_text=page_ocr_texts.get(index, ""),
                    render_map_file_id=(
                        self.uploads.register(render_map_path)
                        if render_map_path is not None
                        else None
                    ),
                    note_index_start=rendered_page.note_index_start,
                    note_index_end=rendered_page.note_index_end,
                    text_blocks=(rendered_text_blocks or {}).get(index, []),
                )
            )
        return pages


def _validate_multi_part_measure_counts(scores: list[JianpuScore]) -> None:
    if len(scores) <= 1:
        return
    counts = [len(score.measures) for score in scores]
    if len(set(counts)) <= 1:
        return
    details = "、".join(
        f"{score.part_name or f'声部{index + 1}'}={counts[index]}"
        for index, score in enumerate(scores)
    )
    raise JianpuValidationError(f"各声部小节数量不一致：{details}")


def _parse_ocr_text(payload: str) -> list[TextBlock]:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"OCR 数据不是有效 JSON：{exc.msg}") from exc
    if not isinstance(raw, list):
        raise ValueError("OCR 数据必须是数组")

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
        if role not in {
            "title",
            "instrument",
            "lyric",
            "expression",
            "footer",
            "measure_number",
            "other",
        }:
            role = "other"
        font_size = item.get("fontSize", item.get("font_size"))
        try:
            font_size = float(font_size) if font_size is not None else None
        except (TypeError, ValueError):
            font_size = None
        blocks.append(TextBlock(text=text, bbox=bbox, role=role, font_size=font_size))
    return blocks


def _serialize_ocr_text(blocks: list[TextBlock], *, id_prefix: str = "ocr") -> str:
    return json.dumps(
        [
            {
                "id": f"{id_prefix}-{index}",
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


def _tag_score_source_page(score: JianpuScore, source_page_index: int) -> None:
    prefix = f"p{source_page_index}|"
    for measure in score.measures:
        measure.source_page_index = source_page_index
        for event in measure.events:
            event.source_ids = [
                source_id if source_id.startswith(prefix) else f"{prefix}{source_id}"
                for source_id in event.source_ids
            ]
            event.source_roles = {
                role: [
                    source_id
                    if source_id.startswith(prefix)
                    else f"{prefix}{source_id}"
                    for source_id in source_ids
                ]
                for role, source_ids in event.source_roles.items()
            }


def _source_ranges_for_scores(scores: list[JianpuScore]) -> list[_SourcePageRange]:
    ranges: list[_SourcePageRange] = []
    for index, score in enumerate(scores):
        starts: list[int] = []
        ends: list[int] = []
        for measure in score.measures:
            start = _measure_number_as_int(measure.display_number)
            if start is None:
                continue
            repeat_count = max(1, int(getattr(measure, "repeat_count", 1) or 1))
            starts.append(start)
            ends.append(start + repeat_count - 1)
        ranges.append(
            _SourcePageRange(
                source_page_index=index,
                start_measure_number=min(starts) if starts else None,
                end_measure_number=max(ends) if ends else None,
            )
        )
    return ranges


def _page_measure_ranges(
    page_ranges: list[A4MeasureRange],
    source_ranges: list[_SourcePageRange],
) -> list[RenderPageMeasureRange]:
    page_start, page_end = _measure_bounds(page_ranges)
    if page_start is None or page_end is None or not source_ranges:
        return [
            RenderPageMeasureRange(
                source_page_index=item.source_page_index,
                start_measure_number=item.start_measure_number,
                end_measure_number=item.end_measure_number,
            )
            for item in page_ranges
        ]
    ranges: list[RenderPageMeasureRange] = []
    for item in source_ranges:
        if item.start_measure_number is None or item.end_measure_number is None:
            continue
        start = max(page_start, item.start_measure_number)
        end = min(page_end, item.end_measure_number)
        if start <= end:
            ranges.append(
                RenderPageMeasureRange(
                    source_page_index=item.source_page_index,
                    start_measure_number=start,
                    end_measure_number=end,
                )
            )
    return ranges or [
        RenderPageMeasureRange(
            source_page_index=item.source_page_index,
            start_measure_number=item.start_measure_number,
            end_measure_number=item.end_measure_number,
        )
        for item in page_ranges
    ]


def _measure_bounds(
    ranges: list[A4MeasureRange],
) -> tuple[int | None, int | None]:
    starts = [
        item.start_measure_number
        for item in ranges
        if item.start_measure_number is not None
    ]
    ends = [
        item.end_measure_number
        for item in ranges
        if item.end_measure_number is not None
    ]
    if not starts or not ends:
        return None, None
    return min(starts), max(ends)


def _resolved_render_page_ocr_texts(
    req: BatchRenderRequest,
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
    *,
    page_offset: int = 0,
    source_page_indices: list[int] | None = None,
) -> dict[int, str]:
    suggested = _suggested_render_page_ocr_texts(
        req,
        measure_ranges_by_page,
        source_page_indices=source_page_indices,
    )
    has_structured_attachments = any(
        page.text_attachments for page in (req.source_pages or req.pages)
    )
    saved = {
        item.page_index: (
            _manual_render_page_ocr_text(item.ocr_text)
            if has_structured_attachments
            else item.ocr_text
        )
        for item in req.render_page_ocr_texts
        if item.page_index >= 0
    }
    saved = {page_index: payload for page_index, payload in saved.items() if payload}
    resolved: dict[int, str] = {}
    for local_index in range(len(measure_ranges_by_page)):
        global_index = page_offset + local_index
        resolved[local_index] = saved.get(global_index, suggested.get(local_index, ""))
    if page_offset == 0 and source_page_indices is None:
        for page_index, ocr_text in saved.items():
            if page_index not in resolved:
                resolved[page_index] = ocr_text
    return resolved


def _suggested_render_page_ocr_texts(
    req: BatchRenderRequest,
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
    *,
    source_page_indices: list[int] | None = None,
) -> dict[int, str]:
    source_pages = req.source_pages or req.pages
    if source_page_indices is None:
        source_page_indices = list(range(len(source_pages)))
    blocks_by_page: dict[int, list[TextBlock]] = {}
    for source_index in source_page_indices:
        if source_index >= len(source_pages):
            continue
        source_page = source_pages[source_index]
        if source_page.text_attachments or not source_page.ocr_text:
            continue
        target_page_index = _first_render_page_for_source(
            measure_ranges_by_page,
            source_index,
        )
        if target_page_index is None:
            target_page_index = min(
                source_index, max(0, len(measure_ranges_by_page) - 1)
            )
        source_blocks = _parse_ocr_text_lenient(source_page.ocr_text)
        placed_blocks = _place_blocks_in_a4_safe_area(source_blocks)
        if placed_blocks:
            blocks_by_page.setdefault(target_page_index, []).extend(placed_blocks)
    return {
        page_index: _serialize_ocr_text(blocks, id_prefix=f"a4p{page_index}")
        for page_index, blocks in blocks_by_page.items()
    }


def _first_render_page_for_source(
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
    source_page_index: int,
) -> int | None:
    for page_index, ranges in enumerate(measure_ranges_by_page):
        if any(item.source_page_index == source_page_index for item in ranges):
            return page_index
    return None


def _parse_ocr_text_lenient(payload: str) -> list[TextBlock]:
    try:
        return _parse_ocr_text(payload)
    except ValueError:
        return []


def _merge_rendered_and_legacy_ocr_texts(
    legacy: dict[int, str],
    rendered: dict[int, list[RenderedTextBlock]],
    page_count: int,
) -> dict[int, str]:
    result: dict[int, str] = {}
    for page_index in range(page_count):
        legacy_items = _load_legacy_ocr_items(legacy.get(page_index, ""))
        rendered_items = [
            {
                "id": block.id,
                "text": block.text,
                "bbox": [
                    block.bbox.x,
                    block.bbox.y,
                    block.bbox.x + block.bbox.width,
                    block.bbox.y + block.bbox.height,
                ],
                "role": block.role,
                "fontSize": block.font_size,
                "sourcePageIndex": block.source_page_index,
                "sourceAttachmentId": block.source_attachment_id,
                "anchor": block.anchor.model_dump(),
            }
            for block in rendered.get(page_index, [])
        ]
        items = [*legacy_items, *rendered_items]
        result[page_index] = json.dumps(items, ensure_ascii=False) if items else ""
    return result


def _load_legacy_ocr_items(payload: str) -> list[dict[str, object]]:
    if not payload.strip():
        return []
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _manual_render_page_ocr_text(payload: str) -> str:
    items = [
        item
        for item in _load_legacy_ocr_items(payload)
        if not item.get("sourceAttachmentId") and not item.get("source_attachment_id")
    ]
    return json.dumps(items, ensure_ascii=False) if items else ""


def _place_blocks_in_a4_safe_area(blocks: list[TextBlock]) -> list[TextBlock]:
    placed: list[TextBlock] = []
    for block in blocks:
        text = block.text.strip()
        if not text or block.role == "measure_number":
            continue
        font_size = _safe_font_size(block.font_size)
        y1 = 120.0 + len(placed) * 30.0
        if y1 > 1754 - 84:
            break
        width = _safe_block_width(block, font_size)
        placed.append(
            TextBlock(
                text=text,
                bbox=(84.0, y1, 84.0 + width, y1 + font_size * 1.35),
                role=block.role,
                font_size=font_size,
            )
        )
    return placed


def _safe_font_size(value: float | None) -> float:
    if value is None:
        return 20.0
    return max(8.0, min(48.0, float(value)))


def _safe_block_width(block: TextBlock, font_size: float) -> float:
    if block.bbox is not None:
        raw_width = abs(block.bbox[2] - block.bbox[0])
    else:
        raw_width = len(block.text.strip()) * font_size * 0.8
    return max(80.0, min(1240 - 84 * 2, raw_width or 80.0))


def _measure_number_as_int(value: object) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _request_measure_number_mode(req) -> MeasureNumberMode:
    if getattr(req, "show_measure_numbers", None) is False:
        return "none"
    return getattr(req, "measure_number_mode", "all")


def _show_measure_numbers(mode: MeasureNumberMode) -> bool:
    return mode != "none"


def _request_show_measure_numbers(req) -> bool:
    return _show_measure_numbers(_request_measure_number_mode(req))


def _renumber_score(score: JianpuScore, start: int) -> None:
    current = start
    for measure in score.measures:
        measure.display_number = current
        for block in measure.text_blocks:
            if block.role == "measure_number":
                block.text = str(current)
                block.measure_number = current
        current += getattr(measure, "repeat_count", 1)


def _renumber_scores_continuously(
    scores: list[JianpuScore],
    *,
    initial_measure_number: int | None = None,
) -> None:
    current: int | None = initial_measure_number
    for score in scores:
        if current is None:
            current = _first_measure_number(score) or 1
        _renumber_score(score, current)
        current += sum(
            getattr(measure, "repeat_count", 1) for measure in score.measures
        )


def _first_measure_number(score: JianpuScore) -> int | None:
    for measure in score.measures:
        raw = str(measure.display_number).strip()
        if raw.isdigit():
            return int(raw)
    return None
