from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ...models.provenance.schemas import SourceMap
from ..overlay.omr_parser import OmrParser

STRUCTURAL_TAGS: frozenset[str] = frozenset(
    {"clef", "time-whole", "time-custom", "key"}
)

# Only expose entities for which the MusicXML patcher has a precise, tested
# operation. Removing a stem, beam or slur by deleting its entire note was both
# surprising and rhythmically destructive.
DELETABLE_TAGS: frozenset[str] = frozenset(
    {"clef", "time-whole", "time-custom", "key", "head", "rest", "alter"}
)


@dataclass(frozen=True, slots=True)
class CorrectableEntity:
    source_id: str
    inter_id: str
    sheet_index: int
    tag: str
    shape: str
    grade: float
    bounds: tuple[int, int, int, int]
    is_structural: bool
    musicxml_attribute: str
    musicxml_locator: str
    hit_path: str
    candidates: tuple[tuple[str, float, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CorrectableSheet:
    sheet_index: int
    width: int
    height: int
    entities: tuple[CorrectableEntity, ...]
    suspicious_glyphs: tuple[tuple[str, tuple[int, int, int, int], str, tuple[tuple[str, float, str], ...]], ...] = ()


def extract_entities(
    omr_path: str | Path,
    source_map: SourceMap,
) -> list[CorrectableSheet]:
    map_sheets = {sheet.sheet_index: sheet for sheet in source_map.sheets}
    result: list[CorrectableSheet] = []
    for omr_sheet in OmrParser().parse(omr_path):
        mapped_sheet = map_sheets.get(omr_sheet.index)
        if mapped_sheet is None:
            continue
        mapped_by_inter = {
            str(element.inter_id): element for element in mapped_sheet.elements
        }
        entities: list[CorrectableEntity] = []
        for inter in omr_sheet.inters:
            if inter.tag not in DELETABLE_TAGS:
                continue
            mapped = mapped_by_inter.get(inter.id)
            if mapped is None:
                continue
            entities.append(
                CorrectableEntity(
                    source_id=mapped.source_id,
                    inter_id=inter.id,
                    sheet_index=omr_sheet.index,
                    tag=inter.tag,
                    shape=inter.shape,
                    grade=inter.grade,
                    bounds=inter.bounds,
                    is_structural=inter.tag in STRUCTURAL_TAGS,
                    musicxml_attribute=mapped.musicxml_locator.attribute,
                    musicxml_locator=mapped.musicxml_locator.contains,
                    hit_path=mapped.hit_path,
                    candidates=(
                        tuple(
                            (candidate.shape, candidate.score, candidate.score_kind)
                            for candidate in mapped.candidates
                        )
                        or ((mapped.shape, mapped.grade, "audiveris_inter_grade"),)
                    ),
                )
            )
        result.append(
            CorrectableSheet(
                sheet_index=omr_sheet.index,
                width=mapped_sheet.width or omr_sheet.width,
                height=mapped_sheet.height or omr_sheet.height,
                entities=tuple(entities),
                suspicious_glyphs=tuple(
                    (
                        glyph.glyph_id,
                        (int(glyph.bounds.x), int(glyph.bounds.y), int(glyph.bounds.width), int(glyph.bounds.height)),
                        glyph.hit_path,
                        tuple((candidate.shape, candidate.score, candidate.score_kind) for candidate in glyph.shape_candidates),
                    )
                    for glyph in (mapped_sheet.glyphs if mapped_sheet else [])
                    if glyph.suspicious
                ),
            )
        )
    return result


def load_source_map(source_map_path: str | Path) -> SourceMap:
    path = Path(source_map_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    source_map = SourceMap.model_validate(data)
    if source_map.version not in {1, 2} or not source_map.sheets:
        raise ValueError("来源映射缺少可编辑的谱面数据")
    return source_map


def entity_index(sheets: list[CorrectableSheet]) -> dict[str, CorrectableEntity]:
    result: dict[str, CorrectableEntity] = {}
    for sheet in sheets:
        for entity in sheet.entities:
            if entity.source_id in result:
                raise ValueError(f"来源映射包含重复标记：{entity.source_id}")
            result[entity.source_id] = entity
    return result
