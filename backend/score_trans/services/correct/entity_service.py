from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ...models.provenance.schemas import BoundingBox, SourceGlyph, SourceMap
from ..overlay.omr_parser import InterData, OmrParser, SheetModel

STRUCTURAL_TAGS: frozenset[str] = frozenset(
    {"clef", "time-whole", "time-custom", "key"}
)

# Only expose entities for which the MusicXML patcher has a precise operation.
# Marks such as ties/slurs are removed from their MusicXML notation nodes; they
# must never be implemented by deleting the note that carries them.
DELETABLE_TAGS: frozenset[str] = frozenset(
    {
        "clef",
        "time-whole",
        "time-custom",
        "key",
        "head",
        "rest",
        "alter",
        "dynamics",
        "dynamic",
        "articulation",
        "ornament",
        "fermata",
        "pause",
        "breath-mark",
        "caesura",
        "slur",
        "tie",
        "tuplet",
        "fingering",
        "plucking",
        "bow",
        "arpeggiato",
        "augmentation-dot",
        "wedge",
        "pedal",
    }
)
CANDIDATE_TAGS: frozenset[str] = frozenset(
    {
        *DELETABLE_TAGS,
        "dynamics",
        "articulation",
        "ornament",
        "fermata",
        "pause",
        "breath-mark",
        "caesura",
        "slur",
        "tuplet",
        "fingering",
        "plucking",
        "bow",
        "arpeggiato",
        "augmentation-dot",
        "wedge",
        "pedal",
    }
)


def _normalized_candidate_score(score: float, score_kind: str) -> float:
    """Map Audiveris' categorical grades and classifier scores to one ranking scale."""
    if score_kind == "audiveris_inter_grade":
        if score >= 3:
            return 1.0  # Evaluation.MANUAL
        if score >= 2:
            return 0.99  # Evaluation.ALGORITHM
    return min(1.0, max(0.0, score)) if math.isfinite(score) else 0.0


def _rank_candidates(
    candidates: tuple[tuple[str, float, str], ...],
    current_shape: str | None = None,
) -> tuple[tuple[str, float, str], ...]:
    normalized = [
        (shape, _normalized_candidate_score(score, kind), kind)
        for shape, score, kind in candidates
    ]
    ranked = sorted(normalized, key=lambda item: item[1], reverse=True)[:5]
    # The recognized shape must stay selectable so a manual switch can be undone,
    # even when five stronger candidates would push it out of the top five.
    if current_shape and all(item[0] != current_shape for item in ranked):
        current = next((item for item in normalized if item[0] == current_shape), None)
        if current is not None:
            if len(ranked) == 5:
                ranked = ranked[:4]
            ranked.append(current)
    return tuple(ranked)


_TAG_FAMILIES: dict[str, str] = {
    "head": "head",
    "unrecognized-head": "head",
    "rest": "rest",
    "alter": "accidental",
    "clef": "clef",
    "key": "key",
    "time-whole": "time",
    "time-custom": "time",
    "time-pair": "time",
    "dynamics": "dynamic",
    "dynamic": "dynamic",
    "wedge": "wedge",
    "articulation": "articulation",
    "ornament": "ornament",
    "fermata": "fermata",
    "pause": "breath",
    "breath-mark": "breath",
    "caesura": "breath",
    "slur": "slur",
    "tie": "slur",
    "tuplet": "tuplet",
    "fingering": "fingering",
    "plucking": "pluck",
    "bow": "bow",
    "arpeggiato": "arpeggio",
    "augmentation-dot": "dot",
    "pedal": "pedal",
}


def _shape_family(shape: str) -> str:
    value = shape.upper()
    if value.startswith(("NOTEHEAD", "WHOLE_NOTE", "BREVE_NOTE", "HALF_NOTE")):
        return "head"
    if "REST" in value:
        return "rest"
    if "CLEF" in value:
        return "clef"
    if value.startswith("KEY_"):
        return "key"
    if value.startswith(("TIME_", "COMMON_TIME", "CUT_TIME")):
        return "time"
    if "SLUR" in value or "TIE" in value:
        return "slur"
    if "TUPLET" in value:
        return "tuplet"
    if value.startswith("DYNAMICS_") or value in {
        "F",
        "P",
        "MP",
        "MF",
        "PP",
        "PPP",
        "SF",
        "SFZ",
        "FFFF",
    }:
        return "dynamic"
    if "FERMATA" in value:
        return "fermata"
    if "AUGMENTATION_DOT" in value or value == "DOT" or value.endswith("_DOT"):
        return "dot"
    if any(part in value for part in ("MARCATO", "ACCENT", "STACCATO", "TENUTO")):
        return "articulation"
    if any(part in value for part in ("MORDENT", "TURN", "TRILL")) or value == "TR":
        return "ornament"
    if "PEDAL" in value:
        return "pedal"
    if value in {"CRESCENDO", "DIMINUENDO"}:
        return "wedge"
    if "ARPEGGIO" in value or value == "ARPEGGIATO":
        return "arpeggio"
    if "PLUCK" in value or "PLECTRUM" in value:
        return "pluck"
    if "BOW" in value or "SCORDATURA" in value:
        return "bow"
    if "FINGERING" in value or value.startswith("DIGIT_"):
        return "fingering"
    if any(part in value for part in ("BREATH", "CAESURA", "PAUSE")):
        return "breath"
    if any(part in value for part in ("SHARP", "FLAT", "NATURAL")):
        return "accidental"
    return "other"


def _candidates_for_family(
    candidates: tuple[tuple[str, float, str], ...], tag: str
) -> tuple[tuple[str, float, str], ...]:
    """Drop stale/corrupt cross-family candidates from older source maps."""
    expected_family = _TAG_FAMILIES.get(tag)
    if expected_family is None:
        return candidates
    return tuple(
        candidate
        for candidate in candidates
        if _shape_family(candidate[0]) == expected_family
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
    staff: str | None = None
    pitch: float | None = None
    can_delete: bool = True
    part_id: str | None = None
    measure_number: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectableGlyph:
    glyph_id: str
    bounds: tuple[int, int, int, int]
    hit_path: str
    candidates: tuple[tuple[str, float, str], ...]
    tag: str
    shape: str
    grade: float
    inter_id: str | None = None
    staff: str | None = None
    pitch: float | None = None
    part_id: str | None = None
    measure_number: str | None = None


@dataclass(frozen=True, slots=True)
class CorrectableSheet:
    sheet_index: int
    width: int
    height: int
    entities: tuple[CorrectableEntity, ...]
    suspicious_glyphs: tuple[CorrectableGlyph, ...] = ()


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
        inters_by_id = {inter.id: inter for inter in omr_sheet.inters}
        entities: list[CorrectableEntity] = []
        for inter in omr_sheet.inters:
            entity_tag = "time-whole" if inter.tag == "time-pair" else inter.tag
            if entity_tag not in CANDIDATE_TAGS:
                continue
            mapped = mapped_by_inter.get(inter.id)
            if mapped is None:
                continue
            staff = inter.staff
            pitch = inter.pitch
            if inter.tag in {"head", "rest"} and (staff is None or pitch is None):
                inferred_staff, inferred_pitch = _staff_pitch(omr_sheet, mapped.bounds)
                staff = staff or inferred_staff
                pitch = pitch if pitch is not None else inferred_pitch
            source_candidates = tuple(
                (candidate.shape, candidate.score, candidate.score_kind)
                for candidate in mapped.candidates
            )
            source_candidates = _candidates_for_family(source_candidates, entity_tag)
            if not source_candidates:
                source_candidates = (
                    (inter.shape or mapped.shape, mapped.grade, "audiveris_inter_grade"),
                )
            entities.append(
                CorrectableEntity(
                    source_id=mapped.source_id,
                    inter_id=inter.id,
                    sheet_index=omr_sheet.index,
                    tag=entity_tag,
                    shape=inter.shape,
                    grade=inter.grade,
                    bounds=inter.bounds,
                    is_structural=entity_tag in STRUCTURAL_TAGS,
                    musicxml_attribute=mapped.musicxml_locator.attribute,
                    musicxml_locator=mapped.musicxml_locator.contains,
                    hit_path=mapped.hit_path,
                    candidates=_rank_candidates(
                        source_candidates,
                        inter.shape or mapped.shape,
                    ),
                    staff=staff,
                    pitch=pitch,
                    can_delete=entity_tag in DELETABLE_TAGS,
                    part_id=mapped.measure.part_id if mapped.measure else None,
                    measure_number=mapped.measure.number if mapped.measure else None,
                )
            )
        glyphs = tuple(
            _correctable_glyph(glyph, omr_sheet, inters_by_id)
            for glyph in mapped_sheet.glyphs
            if glyph.suspicious
        )
        result.append(
            CorrectableSheet(
                sheet_index=omr_sheet.index,
                width=mapped_sheet.width or omr_sheet.width,
                height=mapped_sheet.height or omr_sheet.height,
                entities=tuple(entities),
                suspicious_glyphs=glyphs,
            )
        )
    return result


def _correctable_glyph(
    glyph: SourceGlyph,
    sheet: SheetModel,
    inters_by_id: dict[str, InterData],
) -> CorrectableGlyph:
    mapped = glyph
    inter = (
        inters_by_id.get(str(mapped.inter_id)) if mapped.inter_id is not None else None
    )
    staff = inter.staff if inter is not None else mapped.staff
    pitch = inter.pitch if inter is not None else mapped.pitch
    if staff is None or pitch is None:
        inferred_staff, inferred_pitch = _staff_pitch(sheet, mapped.bounds)
        staff = staff or inferred_staff
        pitch = pitch if pitch is not None else inferred_pitch
    source_candidates = tuple(
        (candidate.shape, candidate.score, candidate.score_kind)
        for candidate in mapped.shape_candidates
    )
    source_candidates = _candidates_for_family(
        source_candidates, inter.tag if inter is not None else mapped.tag
    )
    candidates = _rank_candidates(
        source_candidates,
        mapped.shape if mapped.shape != "UNKNOWN" else None,
    )
    if not candidates and mapped.shape != "UNKNOWN":
        candidates = _rank_candidates(
            ((mapped.shape, mapped.grade, "audiveris_inter_grade"),)
        )
    return CorrectableGlyph(
        glyph_id=mapped.glyph_id,
        bounds=(
            int(mapped.bounds.x),
            int(mapped.bounds.y),
            int(mapped.bounds.width),
            int(mapped.bounds.height),
        ),
        hit_path=mapped.hit_path,
        candidates=candidates,
        tag=inter.tag if inter is not None else mapped.tag,
        shape=inter.shape if inter is not None else mapped.shape,
        grade=inter.grade if inter is not None else mapped.grade,
        inter_id=inter.id if inter is not None else mapped.inter_id,
        staff=staff,
        pitch=pitch,
        part_id=mapped.measure.part_id if mapped.measure else None,
        measure_number=mapped.measure.number if mapped.measure else None,
    )


def _staff_pitch(
    sheet: SheetModel,
    bounds: BoundingBox,
) -> tuple[str | None, float | None]:
    center_x = float(bounds.x) + float(bounds.width) / 2
    center_y = float(bounds.y) + float(bounds.height) / 2
    best: tuple[float, str, float] | None = None
    for staff in sheet.staves:
        if not staff.left <= center_x <= staff.right or len(staff.lines) < 5:
            continue
        line_ys = []
        for x1, y1, x2, y2 in staff.lines:
            ratio = 0.0 if x2 == x1 else (center_x - x1) / (x2 - x1)
            line_ys.append(y1 + (y2 - y1) * ratio)
        gaps = [line_ys[index + 1] - line_ys[index] for index in range(4)]
        spacing = sum(gaps) / len(gaps)
        if spacing <= 0:
            continue
        distance_from_staff = max(line_ys[0] - center_y, center_y - line_ys[-1], 0.0)
        if distance_from_staff > spacing * 3:
            continue
        pitch = (center_y - line_ys[2]) / (spacing / 2)
        rank = abs(pitch)
        if best is None or rank < best[0]:
            best = rank, staff.id, float(round(pitch))
    return (best[1], best[2]) if best is not None else (None, None)


def load_source_map(source_map_path: str | Path) -> SourceMap:
    path = Path(source_map_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    source_map = SourceMap.model_validate(data)
    if source_map.version not in {1, 2, 3} or not source_map.sheets:
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
