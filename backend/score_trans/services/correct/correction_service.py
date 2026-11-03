from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...domain.accidentals import score_with_accidental_mode
from ...domain.parse.musicxml import musicxml_path_to_scores
from ...domain.write.jianpu_text import scores_to_jianpu_document
from ...models.common.types import normalize_instrument_profile
from ...models.correct.schemas import ConversionOptionsDTO
from ...models.provenance.schemas import SourceTextAttachment, TextAnchor
from ...models.score import JianpuScore
from ..render.options import A4LayoutOptions
from ..render.render_service import PublicationRenderService
from .entity_service import CorrectableEntity, CorrectableGlyph
from .musicxml_patch import apply_candidate_selections, apply_deletions


@dataclass(frozen=True, slots=True)
class CorrectionArtifacts:
    working_musicxml: str
    jianpu_text: str
    text_anchors: tuple[TextAnchor, ...]
    text_hash: str
    svg_paths: tuple[Path, ...]
    applied_candidate_selections: dict[str, str]


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
        candidate_selections: dict[str, str] | None = None,
        text_attachments: list[SourceTextAttachment] | None = None,
        glyphs: dict[str, CorrectableGlyph] | None = None,
    ) -> CorrectionArtifacts:
        working_xml = apply_deletions(
            original_musicxml,
            deleted_source_ids,
            entities,
            glyphs or {},
        )
        applied_candidate_selections: dict[str, str] = {}
        working_xml = apply_candidate_selections(
            working_xml,
            candidate_selections or {},
            entities,
            glyphs or {},
            applied_out=applied_candidate_selections,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        musicxml_path = output_dir / "corrected.musicxml"
        musicxml_path.write_text(working_xml, encoding="utf-8")

        scores = musicxml_path_to_scores(
            musicxml_path,
            target_key=options.target_key,
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
        rendered_pages = self.render_service.render_scores_a4_svg_page_results(
            render_scores,
            output_dir / "corrected.svg",
            title=document_title,
            show_measure_numbers=options.show_measure_numbers,
            measure_number_mode=options.measure_number_mode,
            content_scale_percent=options.jianpu_content_scale_percent,
            system_gap_percent=options.jianpu_system_gap_percent,
            short_note_gap_percent=options.jianpu_short_note_gap_percent,
            beat_gap_percent=options.jianpu_beat_gap_percent,
            break_beams_at_beat=options.jianpu_break_beams_at_beat,
            measures_per_system=options.jianpu_measures_per_system,
            layout=A4LayoutOptions(
                content_scale_percent=options.jianpu_content_scale_percent,
                system_gap_percent=options.jianpu_system_gap_percent,
                short_note_gap_percent=options.jianpu_short_note_gap_percent,
                beat_gap_percent=options.jianpu_beat_gap_percent,
                break_beams_at_beat=options.jianpu_break_beams_at_beat,
                measures_per_system=options.jianpu_measures_per_system,
                margin_top_mm=options.jianpu_margin_top_mm,
                margin_bottom_mm=options.jianpu_margin_bottom_mm,
                margin_left_mm=options.jianpu_margin_left_mm,
                margin_right_mm=options.jianpu_margin_right_mm,
                header_gap_mm=options.jianpu_header_gap_mm,
                footer_protection_mm=options.jianpu_footer_protection_mm,
                note_size_percent=options.jianpu_note_size_percent,
                lyric_size_percent=options.jianpu_lyric_size_percent,
                title_size_percent=options.jianpu_title_size_percent,
                annotation_size_percent=options.jianpu_annotation_size_percent,
            ),
        )
        return CorrectionArtifacts(
            working_musicxml=working_xml,
            applied_candidate_selections=applied_candidate_selections,
            jianpu_text=document.text,
            text_anchors=tuple(document.anchors),
            text_hash=document.text_hash,
            svg_paths=tuple(Path(page.path) for page in rendered_pages),
        )


def _document_title(
    options: ConversionOptionsDTO,
    attachments: list[SourceTextAttachment],
    scores: list[JianpuScore],
) -> str | None:
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
    return scores[0].title if scores and scores[0].title else None
