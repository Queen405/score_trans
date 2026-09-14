from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from ...models.correct.schemas import (
    CorrectionRequest,
    CorrectionResponse,
    CorrectableEntityDTO,
    EntitiesResponse,
    SheetEntitiesDTO,
)
from ...services.correct.correction_service import CorrectionService
from ...services.correct.entity_service import (
    CorrectableSheet,
    entity_index,
    extract_entities,
    load_source_map,
)
from ...services.files.upload_service import UploadService
from ...utils.warnings import collect_warnings, dedupe_preserve_order


class CorrectActions:
    def __init__(
        self,
        uploads: UploadService | None = None,
        correction_service: CorrectionService | None = None,
    ) -> None:
        self.uploads = uploads or UploadService()
        self.correction_service = correction_service or CorrectionService()

    def get_entities(
        self,
        omr_file_id: str,
        source_map_file_id: str,
    ) -> EntitiesResponse:
        return _to_entities_response(
            self._load_entities(omr_file_id, source_map_file_id)
        )

    def apply_corrections(self, req: CorrectionRequest) -> CorrectionResponse:
        entities = entity_index(
            self._load_entities(req.omr_file_id, req.source_map_file_id)
        )
        with TemporaryDirectory(prefix="score-trans-correct-") as temp_dir:
            with collect_warnings() as captured:
                artifacts = self.correction_service.correct(
                    req.original_musicxml,
                    req.deleted_source_ids,
                    entities,
                    req.options,
                    Path(temp_dir),
                    req.text_attachments,
                )
            svg_file_ids = [self.uploads.register(path) for path in artifacts.svg_paths]
        return CorrectionResponse(
            working_musicxml=artifacts.working_musicxml,
            jianpu_text=artifacts.jianpu_text,
            text_anchors=list(artifacts.text_anchors),
            text_hash=artifacts.text_hash,
            svg_file_ids=svg_file_ids,
            warnings=dedupe_preserve_order(captured),
        )

    def _load_entities(
        self,
        omr_file_id: str,
        source_map_file_id: str,
    ) -> list[CorrectableSheet]:
        omr_path = self.uploads.get_path(omr_file_id)
        if not omr_path or not Path(omr_path).is_file():
            raise FileNotFoundError(f"OMR 文件不存在：{omr_file_id}")
        source_map_path = self.uploads.get_path(source_map_file_id)
        if not source_map_path or not Path(source_map_path).is_file():
            raise FileNotFoundError(f"来源映射文件不存在：{source_map_file_id}")
        sheets = extract_entities(omr_path, load_source_map(source_map_path))
        if not sheets or not any(sheet.entities for sheet in sheets):
            raise ValueError("该识别结果不包含可安全编辑的 MusicXML 定位信息")
        return sheets


def _to_entities_response(sheets: list[CorrectableSheet]) -> EntitiesResponse:
    return EntitiesResponse(
        sheets=[
            SheetEntitiesDTO(
                sheet_index=sheet.sheet_index,
                width=sheet.width,
                height=sheet.height,
                entities=[
                    CorrectableEntityDTO(
                        source_id=entity.source_id,
                        inter_id=entity.inter_id,
                        sheet_index=entity.sheet_index,
                        tag=entity.tag,
                        shape=entity.shape,
                        grade=entity.grade,
                        bounds_x=entity.bounds[0],
                        bounds_y=entity.bounds[1],
                        bounds_w=entity.bounds[2],
                        bounds_h=entity.bounds[3],
                        is_structural=entity.is_structural,
                        musicxml_locator=entity.musicxml_locator,
                        hit_path=entity.hit_path,
                    )
                    for entity in sheet.entities
                ],
            )
            for sheet in sheets
        ]
    )
