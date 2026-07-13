from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ...models.provenance.schemas import SourceMap
from ..overlay.omr_parser import OmrParser

STRUCTURAL_TAGS: frozenset[str] = frozenset({
    "clef",
    "time-whole",
    "time-custom",
    "key",
})

DELETABLE_TAGS: frozenset[str] = frozenset({
    "clef", "time-whole", "time-custom", "key",
    "head", "rest", "alter",
    "augmentation-dot", "stem", "beam", "beam-hook", "flag",
    "slur", "articulation", "tuplet", "bow",
})


@dataclass(slots=True)
class CorrectableEntity:
    source_id: str
    inter_id: str
    sheet_index: int
    tag: str
    shape: str
    grade: float
    bounds: tuple[int, int, int, int]
    is_structural: bool
    musicxml_locator: str | None = None
    hit_path: str | None = None


def extract_entities(
    omr_path: str | Path,
    source_map: SourceMap | None,
) -> list[list[CorrectableEntity]]:
    sheets = OmrParser().parse(omr_path)

    locator_map: dict[str, str] = {}
    hit_path_map: dict[str, str] = {}
    if source_map:
        for sheet in source_map.sheets:
            for elem in sheet.elements:
                locator_map[str(elem.inter_id)] = elem.musicxml_locator.contains
                hit_path_map[str(elem.inter_id)] = elem.hit_path

    result: list[list[CorrectableEntity]] = []
    for sheet in sheets:
        entities: list[CorrectableEntity] = []
        for inter in sheet.inters:
            if inter.tag not in DELETABLE_TAGS:
                continue
            inter_id_str = inter.id
            source_id = f"s{sheet.index}:i{inter_id_str}"
            entities.append(CorrectableEntity(
                source_id=source_id,
                inter_id=inter_id_str,
                sheet_index=sheet.index,
                tag=inter.tag,
                shape=inter.shape,
                grade=inter.grade,
                bounds=inter.bounds,
                is_structural=inter.tag in STRUCTURAL_TAGS,
                musicxml_locator=locator_map.get(inter_id_str),
                hit_path=hit_path_map.get(inter_id_str),
            ))
        result.append(entities)
    return result


def load_source_map(source_map_path: str | Path) -> SourceMap | None:
    try:
        data = json.loads(Path(source_map_path).read_text(encoding="utf-8"))
        return SourceMap.model_validate(data)
    except Exception:
        return None
