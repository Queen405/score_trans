from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...domain.accidentals import score_with_accidental_mode
from ...domain.parse.musicxml import musicxml_path_to_scores
from ...domain.text_placement import place_source_text_attachments
from ...domain.write.jianpu_text import scores_to_jianpu_document
from ...models.correct.schemas import ConversionOptionsDTO
from ...models.provenance.schemas import SourceTextAttachment, TextAnchor
from ...models.render.schemas import RenderPageMeasureRange
from ...models.score import JianpuScore
from ...models.common.types import normalize_instrument_profile
from ..render.render_service import PublicationRenderService
from .entity_service import CorrectableEntity
from .musicxml_patch import apply_deletions


@dataclass(frozen=True, slots=True)
class CorrectionArtifacts:
    working_musicxml: str
    jianpu_text: str
    text_anchors: tuple[TextAnchor, ...]
    text_hash: str
    svg_paths: tuple[Path, ...]


class CorrectionService:
    def __init__(
        self,
        render_service: PublicationRenderService | None = None,
    ) -> None:
        self.render_service = render_service or PublicationRenderService()

    def correct(
        self,
        original_musicxml: str,
        deleted_source_ids: list[str],
        entities: dict[str, CorrectableEntity],
        options: ConversionOptionsDTO,
        output_dir: Path,
        text_attachments: list[SourceTextAttachment] | None = None,
    ) -> CorrectionArtifacts:
        working_xml = apply_deletions(
            original_musicxml,
            deleted_source_ids,
            entities,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        musicxml_path = output_dir / "corrected.musicxml"
        musicxml_path.write_text(working_xml, encoding="utf-8")

        scores = musicxml_path_to_scores(
            musicxml_path,
            target_key=options.target_key,
            start_measure_number=options.start_measure_number,
            instrument_profile=normalize_instrument_profile(options.instrument_profile),
        )
        attachments = text_attachments or []
        document_title = _document_title(options, attachments, scores)
        if document_title:
            for score in scores:
                score.title = document_title

        document = scores_to_jianpu_document(
            scores,
            accidental_mode=options.accidental_mode,
        )
        render_scores = [
            score_with_accidental_mode(
                score,
                accidental_mode=options.accidental_mode,
            )
            for score in scores
        ]
        layout_pages = self.render_service.build_scores_a4_svg_pages(
            render_scores,
            title=document_title,
            show_measure_numbers=options.show_measure_numbers,
            measure_number_mode=options.measure_number_mode,
        )
        placement_attachments = [
            attachment for attachment in attachments if attachment.role != "title"
        ]
        placement = place_source_text_attachments(
            [placement_attachments],
            [page.svg for page in layout_pages],
            [
                [
                    RenderPageMeasureRange(
                        source_page_index=item.source_page_index,
                        start_measure_number=item.start_measure_number,
                        end_measure_number=item.end_measure_number,
                    )
                    for item in page.measure_ranges
                ]
                for page in layout_pages
            ],
        )
        rendered_pages = self.render_service.render_scores_a4_svg_page_results(
            render_scores,
            output_dir / "corrected.svg",
            title=document_title,
            show_measure_numbers=options.show_measure_numbers,
            measure_number_mode=options.measure_number_mode,
            page_text_blocks=placement.text_blocks_by_page,
        )
        return CorrectionArtifacts(
            working_musicxml=working_xml,
            jianpu_text=document.text,
            text_anchors=tuple(document.anchors),
            text_hash=document.text_hash,
            svg_paths=tuple(Path(page.path) for page in rendered_pages),
        )


def _document_title(
    options: ConversionOptionsDTO,
    attachments: list[SourceTextAttachment],
    scores: list[JianpuScore],
) -> str:
    if options.title and options.title.strip():
        return options.title.strip()
    attachment_title = next(
        (
            attachment.text.strip()
            for attachment in attachments
            if attachment.role == "title" and attachment.text.strip()
        ),
        "",
    )
    if attachment_title:
        return attachment_title
    return scores[0].title if scores and scores[0].title else "简谱"
