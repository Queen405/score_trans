from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import cast

from ...domain.parse.musicxml import musicxml_path_to_scores
from ...domain.write.jianpu_text import scores_to_jianpu_document
from ...domain.accidentals import score_with_accidental_mode
from ...models.correct.schemas import (
    ConversionOptionsDTO,
    CorrectionRequest,
    CorrectionResponse,
    CorrectableEntityDTO,
    EntitiesResponse,
    SheetEntitiesDTO,
)
from ...models.common.types import (
    AccidentalMode,
    InstrumentProfile,
    MeasureNumberMode,
    normalize_instrument_profile,
)
from ...services.correct.entity_service import (
    CorrectableEntity,
    extract_entities,
    load_source_map,
)
from ...services.correct.musicxml_patch import apply_deletions
from ...services.files.upload_service import UploadService
from ...services.render.render_service import PublicationRenderService


class CorrectActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        render_service: PublicationRenderService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.render_service = render_service or PublicationRenderService()

    def get_entities(
        self,
        omr_file_id: str,
        source_map_file_id: str | None = None,
    ) -> EntitiesResponse:
        omr_path = self.uploads.get_path(omr_file_id)
        if not omr_path or not Path(omr_path).exists():
            raise FileNotFoundError(f"OMR file not found: {omr_file_id}")
        source_map = None
        if source_map_file_id:
            sm_path = self.uploads.get_path(source_map_file_id)
            if sm_path and Path(sm_path).exists():
                source_map = load_source_map(sm_path)
        sheets = extract_entities(omr_path, source_map)
        return _to_entities_response(sheets)

    def apply_corrections(self, req: CorrectionRequest) -> CorrectionResponse:
        entity_index = self._build_entity_index(req)
        working_xml = apply_deletions(
            req.original_musicxml,
            req.deleted_source_ids,
            entity_index,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".musicxml", delete=False, encoding="utf-8"
        ) as f:
            f.write(working_xml)
            tmp_path = Path(f.name)

        try:
            opts = req.options
            scores = musicxml_path_to_scores(
                tmp_path,
                target_key=opts.target_key,
                start_measure_number=opts.start_measure_number,
                instrument_profile=normalize_instrument_profile(opts.instrument_profile),
            )
            if opts.title:
                for score in scores:
                    score.title = opts.title

            accidental_mode = cast(AccidentalMode, opts.accidental_mode)
            measure_number_mode = cast(MeasureNumberMode, opts.measure_number_mode)
            document = scores_to_jianpu_document(
                scores,
                accidental_mode=accidental_mode,
            )

            render_scores = [
                score_with_accidental_mode(score, accidental_mode=accidental_mode)
                for score in scores
            ]
            rendered_pages = self.render_service.render_scores_a4_svg_pages(
                render_scores,
                Path(tempfile.mkdtemp()) / "output.svg",
                title=opts.title or (render_scores[0].title if render_scores else "简谱"),
                show_measure_numbers=opts.show_measure_numbers,
                measure_number_mode=measure_number_mode,
            )
            svg_file_ids = [
                self.uploads.register(Path(str(getattr(p, "path", p))))
                for p in rendered_pages
            ]
        finally:
            tmp_path.unlink(missing_ok=True)

        return CorrectionResponse(
            working_musicxml=working_xml,
            jianpu_text=document.text,
            text_anchors=[a.model_dump() for a in document.anchors],
            text_hash=document.text_hash,
            svg_file_ids=svg_file_ids,
        )

    def _build_entity_index(self, req: CorrectionRequest) -> dict[str, dict]:
        if not req.source_map_file_id:
            return {}
        sm_path = self.uploads.get_path(req.source_map_file_id)
        if not sm_path or not Path(sm_path).exists():
            return {}
        omr_path = None
        source_map = load_source_map(sm_path)
        index: dict[str, dict] = {}
        if source_map:
            for sheet in source_map.sheets:
                for elem in sheet.elements:
                    index[elem.source_id] = {
                        "tag": "",
                        "shape": elem.shape,
                        "musicxml_locator": elem.musicxml_locator.contains,
                    }
        return index


def _to_entities_response(sheets: list[list[CorrectableEntity]]) -> EntitiesResponse:
    result_sheets: list[SheetEntitiesDTO] = []
    for sheet_entities in sheets:
        if not sheet_entities:
            continue
        entities = [
            CorrectableEntityDTO(
                source_id=e.source_id,
                inter_id=e.inter_id,
                sheet_index=e.sheet_index,
                tag=e.tag,
                shape=e.shape,
                grade=e.grade,
                bounds_x=e.bounds[0],
                bounds_y=e.bounds[1],
                bounds_w=e.bounds[2],
                bounds_h=e.bounds[3],
                is_structural=e.is_structural,
                musicxml_locator=e.musicxml_locator,
                hit_path=e.hit_path,
            )
            for e in sheet_entities
        ]
        result_sheets.append(SheetEntitiesDTO(
            sheet_index=sheet_entities[0].sheet_index,
            width=0,
            height=0,
            entities=entities,
        ))
    return EntitiesResponse(sheets=result_sheets)
