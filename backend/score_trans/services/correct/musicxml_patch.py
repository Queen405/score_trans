from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
import statistics
import xml.etree.ElementTree as ET
from fractions import Fraction

from ...utils.safe_xml import safe_xml_fromstring
from .clef_transform import transform_pitch
from .entity_service import CorrectableEntity, CorrectableGlyph

logger = logging.getLogger(__name__)


def apply_deletions(
    original_musicxml: str,
    deleted_source_ids: list[str],
    entities: Mapping[str, CorrectableEntity],
    glyphs: Mapping[str, CorrectableGlyph] | None = None,
) -> str:
    root = safe_xml_fromstring(
        original_musicxml.encode("utf-8"),
        allow_musicxml_doctype=True,
    )
    ns = _detect_namespace(root)

    glyph_index = glyphs or {}
    unknown = [
        source_id
        for source_id in deleted_source_ids
        if source_id not in entities and source_id not in glyph_index
    ]
    if unknown:
        raise ValueError(f"无法定位待删除标记：{', '.join(unknown)}")

    for source_id in dict.fromkeys(deleted_source_ids):
        # A loose glyph has no MusicXML node until a candidate is inserted.
        # Recording its deletion suppresses that candidate insertion in the UI;
        # there is therefore nothing to patch in the base MusicXML here.
        entity = entities.get(source_id)
        if entity is None:
            continue
        if entity.tag == "clef":
            _delete_clef_with_pitch_transform(root, ns, entity)
        elif entity.tag in {"time-whole", "time-custom"}:
            _delete_attribute_element(root, entity, "time")
        elif entity.tag == "key":
            _delete_attribute_element(root, entity, "key")
        elif entity.tag == "head":
            _replace_note_head_with_rest(root, ns, entity)
        elif entity.tag == "rest":
            _remove_note(root, ns, entity)
        elif entity.tag == "alter":
            _remove_accidental(root, ns, entity)
        elif entity.tag in {
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
        }:
            _remove_notation_mark(root, ns, entity)
        else:  # Defensive: entity_service must never expose unsupported tags.
            raise ValueError(f"不支持删除的标记类型：{entity.tag}")

    return _serialize(root, ns)


def apply_candidate_selections(
    original_musicxml: str,
    selections: Mapping[str, str],
    entities: Mapping[str, CorrectableEntity],
    glyphs: Mapping[str, CorrectableGlyph] | None = None,
    applied_out: dict[str, str] | None = None,
) -> str:
    """Apply selected classifications and insert notes selected from loose glyphs.

    Notehead class changes also update MusicXML type and duration so the
    regenerated Jianpu reflects the chosen quarter/half/whole-note value. The
    correction intentionally does not validate measure rhythm.

    Selections that actually reach the MusicXML are collected into
    ``applied_out``, so a phantom locator cannot be reported as applied.
    """
    applied: dict[str, str] = {}
    if not selections:
        return original_musicxml
    root = safe_xml_fromstring(
        original_musicxml.encode("utf-8"), allow_musicxml_doctype=True
    )
    ns = _detect_namespace(root)
    glyph_index = glyphs or {}
    for source_id, selected_shape in selections.items():
        entity = entities.get(source_id)
        if entity is None:
            glyph = glyph_index.get(source_id)
            if glyph is None:
                raise ValueError(f"无法定位待应用候选：{source_id}")
            candidates = {shape for shape, _score, _kind in glyph.candidates}
            if selected_shape not in candidates:
                raise ValueError(f"标记 {source_id} 不包含候选形状：{selected_shape}")
            if glyph.tag == "rest":
                _insert_glyph_rest(root, ns, glyph, selected_shape, entities)
            else:
                _insert_glyph_note(root, ns, glyph, selected_shape, entities)
            applied[source_id] = selected_shape
            continue
        candidates = {shape for shape, _score, _kind in entity.candidates}
        if selected_shape not in candidates:
            raise ValueError(f"标记 {source_id} 不包含候选形状：{selected_shape}")
        if entity.tag in {"head", "rest"} and not _matching_elements(root, entity):
            _insert_unexported_entity(root, ns, entity, selected_shape, entities)
            applied[source_id] = selected_shape
            continue
        if _apply_entity_candidate(root, ns, entity, selected_shape, entities):
            applied[source_id] = selected_shape
        else:
            logger.warning("候选未写入 MusicXML，计为未应用：%s", source_id)
    if applied_out is not None:
        applied_out.update(applied)
    return _serialize(root, ns)


def _insert_unexported_entity(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> None:
    """Add a source-map note/rest that Audiveris omitted from exported MusicXML."""
    glyph = CorrectableGlyph(
        glyph_id=entity.source_id,
        bounds=entity.bounds,
        hit_path=entity.hit_path,
        candidates=entity.candidates,
        tag=entity.tag,
        shape=entity.shape,
        grade=entity.grade,
        inter_id=entity.inter_id,
        staff=entity.staff,
        pitch=entity.pitch,
    )
    if entity.tag == "rest":
        _insert_glyph_rest(root, ns, glyph, selected_shape, entities)
    else:
        _insert_glyph_note(root, ns, glyph, selected_shape, entities)


def _apply_entity_candidate(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> bool:
    if entity.tag == "slur":
        return _replace_slur_candidate(root, ns, entity, selected_shape)
    if entity.tag == "tuplet":
        return _replace_tuplet_candidate(root, ns, entity, selected_shape)
    if entity.tag == "wedge":
        return _replace_wedge_candidate(root, ns, entity, selected_shape)
    if entity.tag == "pedal":
        target = _single_matching_element(root, entity)
        return _replace_pedal_candidate(
            root, ns, target, entity, selected_shape, entities
        )
    target = _single_matching_element(root, entity)
    if target is None and entity.tag != "clef":
        logger.warning("跳过无法定位的候选：%s", entity.source_id)
        return False
    if entity.tag == "head":
        current_note_type = _notehead_type(entity.shape)
        selected_type = _notehead_type(selected_shape)
        if selected_type is None:
            raise ValueError(f"暂不支持音符头候选：{selected_shape}")
        note = _ancestor(root, target, _q(ns, "note"))
        if note is None:
            raise ValueError(f"标记 {entity.source_id} 未定位到音符")
        notehead_style = _musicxml_notehead_style(selected_shape)
        notehead = note.find(_q(ns, "notehead"))
        if notehead_style == "normal":
            if notehead is not None:
                note.remove(notehead)
        else:
            if notehead is None:
                notehead = ET.Element(_q(ns, "notehead"))
                _insert_note_child(
                    note,
                    ns,
                    notehead,
                    {
                        "notehead-text",
                        "staff",
                        "beam",
                        "notations",
                        "lyric",
                        "play",
                        "listen",
                    },
                )
            notehead.text = notehead_style
        # Audiveris stores chord members as separate MusicXML notes, while the
        # Jianpu converter reads one duration for the chord. A selected head
        # therefore changes the duration of the whole chord event, including
        # when the clicked head is a <chord/> follower. Preserve the existing
        # MusicXML rhythm when only the head style changes within the same
        # filled/hollow/whole duration family.
        if current_note_type != selected_type:
            for chord_note in _chord_notes(root, ns, note):
                existing_type = chord_note.findtext(_q(ns, "type")) or current_note_type
                _replace_note_type_and_duration(
                    chord_note, ns, existing_type, selected_type
                )
        return True
    if entity.tag == "rest":
        _replace_rest_candidate(root, ns, target, entity, selected_shape)
        return True
    if entity.tag == "alter":
        _replace_alter_candidate(root, ns, target, entity, selected_shape)
        return True
    if entity.tag == "clef":
        return _replace_clef_candidate(
            root, ns, target, entity, selected_shape, entities
        )
    if entity.tag == "key":
        _replace_key_candidate(root, ns, target, entity, selected_shape)
        return True
    if entity.tag in {"time-whole", "time-custom"}:
        _replace_time_candidate(root, ns, target, entity, selected_shape)
        return True
    if entity.tag in {"dynamics", "dynamic"}:
        _replace_dynamic_candidate(root, ns, target, entity, selected_shape)
        return True
    if entity.tag == "articulation":
        _replace_notation_candidate(
            root, ns, target, entity, selected_shape, "articulation"
        )
        return True
    if entity.tag == "ornament":
        _replace_notation_candidate(
            root, ns, target, entity, selected_shape, "ornament"
        )
        return True
    if entity.tag == "fermata":
        _replace_notation_candidate(root, ns, target, entity, selected_shape, "fermata")
        return True
    if entity.tag in {"pause", "breath-mark", "caesura"}:
        _replace_notation_candidate(root, ns, target, entity, selected_shape, "pause")
        return True
    if entity.tag == "fingering":
        _replace_technical_candidate(
            root, ns, target, entity, selected_shape, "fingering"
        )
        return True
    if entity.tag == "plucking":
        _replace_technical_candidate(root, ns, target, entity, selected_shape, "pluck")
        return True
    if entity.tag == "bow":
        _replace_technical_candidate(root, ns, target, entity, selected_shape, "bow")
        return True
    if entity.tag == "arpeggiato":
        _replace_notation_candidate(
            root, ns, target, entity, selected_shape, "arpeggiato"
        )
        return True
    if entity.tag == "augmentation-dot":
        _replace_augmentation_dot(root, ns, target, entity, selected_shape)
        return True
    raise ValueError(f"暂不支持该标记的候选替换：{entity.tag}")


def _matching_notes(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
) -> list[ET.Element]:
    notes: list[ET.Element] = []
    for target in _matching_elements(root, entity):
        note = _ancestor(root, target, _q(ns, "note"))
        if note is not None and note not in notes:
            notes.append(note)
    return notes


def _chord_notes(root: ET.Element, ns: str, note: ET.Element) -> list[ET.Element]:
    """Return the MusicXML notes that encode the same chord onset as ``note``."""
    measure = _ancestor(root, note, _q(ns, "measure"))
    if measure is None:
        return [note]
    notes = list(measure.findall(_q(ns, "note")))
    try:
        index = notes.index(note)
    except ValueError:
        return [note]
    first = index
    while first > 0 and notes[first].find(_q(ns, "chord")) is not None:
        first -= 1
    last = first + 1
    while last < len(notes) and notes[last].find(_q(ns, "chord")) is not None:
        last += 1
    return notes[first:last]


@dataclass(frozen=True, slots=True)
class _Column:
    """MusicXML 里同一 onset 的一组 note（和弦列）。"""

    center: float
    head: ET.Element
    tail: ET.Element
    voice: str
    staff: str


@dataclass(frozen=True, slots=True)
class _AnchorContext:
    """插入未识别符号时用到的上下文：候选列、最近锚点与几何容差。"""

    anchors: list[tuple[CorrectableEntity, ET.Element, ET.Element]]
    columns: list[_Column]
    nearest_entity: CorrectableEntity
    nearest_note: ET.Element
    measure: ET.Element
    glyph_x: float
    glyph_y: float
    tolerance: float


# 二度叠置的和弦音会有约 0.6~1 个符头宽的横向错位，1.25 倍作为上限。
_CHORD_HEAD_WIDTH_RATIO = 1.25


def _xml_voice(ns: str, note: ET.Element) -> str:
    return (note.findtext(_q(ns, "voice")) or "1").strip() or "1"


def _xml_staff(ns: str, note: ET.Element) -> str:
    return (note.findtext(_q(ns, "staff")) or "1").strip() or "1"


def _column_tolerance(
    anchors: list[tuple[CorrectableEntity, ET.Element, ET.Element]],
    columns: list[_Column],
) -> float:
    """同列判定容差：取「半列距」与「1.25 倍符头宽」的较小值。

    后端拿不到 interline，因此用版面自身的量做尺度：符头宽度来自 OMR bounds，
    列距来自同一小节内相邻和弦列的中心距。两者都随扫描分辨率自适应。
    """
    widths = [item[0].bounds[2] for item in anchors if item[0].bounds[2] > 0]
    head_width = statistics.median(widths) if widths else 12.0
    centers = sorted({column.center for column in columns})
    gaps = sorted(
        right - left for left, right in zip(centers, centers[1:]) if right - left > 1.0
    )
    # 用第 10 百分位列距而不是最小列距：个别被拆开的和弦音会把最小列距压到几像素，
    # 从而把容差压没；p10 仍能挡住真正的相邻列（约半列距）。
    column_gap = gaps[max(0, len(gaps) // 10)] if gaps else 2.5 * head_width
    return max(3.0, min(0.5 * column_gap, _CHORD_HEAD_WIDTH_RATIO * head_width))


def _replace_slur_candidate(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
) -> bool:
    placement = (
        "above"
        if selected_shape.upper().endswith("_ABOVE")
        else "below"
        if selected_shape.upper().endswith("_BELOW")
        else None
    )
    changed = False
    for note in _matching_notes(root, ns, entity):
        notations = note.find(_q(ns, "notations"))
        if notations is None:
            continue
        for slur in notations.findall(_q(ns, "slur")):
            if placement:
                slur.set("placement", placement)
            else:
                slur.attrib.pop("placement", None)
            changed = True
    if not changed:
        logger.warning("跳过无法定位的连线候选 %s", entity.source_id)
    return changed


def _replace_tuplet_candidate(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
) -> bool:
    counts = {"TUPLET_THREE": (3, 2), "TUPLET_SIX": (6, 4)}.get(selected_shape.upper())
    if counts is None:
        raise ValueError(f"暂不支持连音候选：{selected_shape}")
    actual_count, normal_count = counts
    matched_notes = _matching_notes(root, ns, entity)
    changed = False
    measures: list[ET.Element] = []
    for note in matched_notes:
        measure = _ancestor(root, note, _q(ns, "measure"))
        if measure is not None and measure not in measures:
            measures.append(measure)
        notations = note.find(_q(ns, "notations"))
        if notations is None:
            continue
        for tuplet in notations.findall(_q(ns, "tuplet")):
            for number in tuplet.findall(
                f"{_q(ns, 'tuplet-actual')}/{_q(ns, 'tuplet-number')}"
            ):
                number.text = str(actual_count)
                changed = True
            for number in tuplet.findall(
                f"{_q(ns, 'tuplet-normal')}/{_q(ns, 'tuplet-number')}"
            ):
                number.text = str(normal_count)
                changed = True

    # The Jianpu parser reads the ratio from time-modification, not from the
    # printed tuplet number. Update every encoded note between the matched
    # start/stop notes so the visual mark and the regenerated rhythm agree.
    for measure in measures:
        measure_notes = list(measure.findall(_q(ns, "note")))
        matched_indices = [
            index for index, note in enumerate(measure_notes) if note in matched_notes
        ]
        if not matched_indices:
            continue
        start_indices = [
            index
            for index in matched_indices
            if any(
                tuplet.get("type") == "start"
                for tuplet in measure_notes[index].findall(
                    f"{_q(ns, 'notations')}/{_q(ns, 'tuplet')}"
                )
            )
        ]
        stop_indices = [
            index
            for index in matched_indices
            if any(
                tuplet.get("type") == "stop"
                for tuplet in measure_notes[index].findall(
                    f"{_q(ns, 'notations')}/{_q(ns, 'tuplet')}"
                )
            )
        ]
        start = min(start_indices or matched_indices)
        stop = max(stop_indices or matched_indices)
        for note in measure_notes[start : stop + 1]:
            modification = note.find(_q(ns, "time-modification"))
            if modification is None:
                continue
            actual = modification.find(_q(ns, "actual-notes"))
            normal = modification.find(_q(ns, "normal-notes"))
            if actual is not None:
                actual.text = str(actual_count)
                changed = True
            if normal is not None:
                normal.text = str(normal_count)
                changed = True
    if not changed:
        logger.warning("跳过无法定位的连音候选 %s", entity.source_id)
    return changed


def _replace_technical_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
    family: str,
) -> None:
    note = _ancestor(root, target, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到音符")
    technical = note.find(f"{_q(ns, 'notations')}/{_q(ns, 'technical')}")
    if technical is None:
        notations = note.find(_q(ns, "notations"))
        if notations is None:
            notations = ET.SubElement(note, _q(ns, "notations"))
        technical = ET.SubElement(notations, _q(ns, "technical"))

    shape = selected_shape.upper()
    if family == "fingering":
        if not shape.startswith("DIGIT_") or shape.removeprefix("DIGIT_") not in set(
            "012345"
        ):
            raise ValueError(f"暂不支持指法候选：{selected_shape}")
        for child in list(technical.findall(_q(ns, "fingering"))):
            technical.remove(child)
        ET.SubElement(technical, _q(ns, "fingering")).text = shape[-1]
        return
    if family == "pluck":
        pluck = {"PLUCK_P": "p", "PLUCK_I": "i", "PLUCK_M": "m", "PLUCK_A": "a"}.get(
            shape
        )
        if pluck is None:
            raise ValueError(f"暂不支持拨弦候选：{selected_shape}")
        for child in list(technical.findall(_q(ns, "pluck"))):
            technical.remove(child)
        ET.SubElement(technical, _q(ns, "pluck")).text = pluck
        return
    bow_tag = {"BOW_UP": "up-bow", "BOW_DOWN": "down-bow"}.get(shape)
    if bow_tag is None:
        raise ValueError(f"暂不支持弓法候选：{selected_shape}")
    for name in ("up-bow", "down-bow"):
        for child in list(technical.findall(_q(ns, name))):
            technical.remove(child)
    ET.SubElement(technical, _q(ns, bow_tag))


def _replace_augmentation_dot(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    if selected_shape.upper() != "AUGMENTATION_DOT":
        raise ValueError(f"暂不支持附点候选：{selected_shape}")
    note = _ancestor(root, target, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到音符")
    if note.find(_q(ns, "dot")) is None:
        type_element = note.find(_q(ns, "type"))
        dot = ET.Element(_q(ns, "dot"))
        note.insert(
            list(note).index(type_element) + 1
            if type_element is not None
            else len(note),
            dot,
        )


def _insert_glyph_note(
    root: ET.Element,
    ns: str,
    glyph: CorrectableGlyph,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> None:
    note_type = _notehead_type(selected_shape)
    if note_type is None:
        raise ValueError(f"未识别符号暂不支持该候选：{selected_shape}")
    if glyph.staff is None or glyph.pitch is None:
        raise ValueError(f"无法确定未识别符号 {glyph.glyph_id} 所在的谱表音高")

    context = _glyph_note_context(root, ns, glyph, entities, require_pitch=True)
    nearest_entity = context.nearest_entity
    nearest_note = context.nearest_note
    measure = context.measure
    pitch_element = nearest_note.find(_q(ns, "pitch"))
    step_element = (
        pitch_element.find(_q(ns, "step")) if pitch_element is not None else None
    )
    octave_element = (
        pitch_element.find(_q(ns, "octave")) if pitch_element is not None else None
    )
    if step_element is None or octave_element is None or not step_element.text:
        raise ValueError(f"附近音符缺少可用音高：{nearest_entity.source_id}")
    target_step, target_octave = _shift_diatonic_pitch(
        step_element.text,
        int(octave_element.text or "4"),
        round(nearest_entity.pitch - glyph.pitch),
    )

    divisions = _measure_divisions(root, ns, measure)
    note = ET.Element(_q(ns, "note"))
    note.set("id", _unique_note_id(root, glyph.glyph_id))
    pitch = ET.SubElement(note, _q(ns, "pitch"))
    ET.SubElement(pitch, _q(ns, "step")).text = target_step
    ET.SubElement(pitch, _q(ns, "octave")).text = str(target_octave)
    ET.SubElement(note, _q(ns, "duration")).text = str(
        divisions * {"quarter": 1, "half": 2, "whole": 4}[note_type]
    )
    voice = nearest_note.find(_q(ns, "voice"))
    if voice is not None:
        voice_copy = ET.SubElement(note, _q(ns, "voice"))
        voice_copy.text = voice.text
    ET.SubElement(note, _q(ns, "type")).text = note_type
    staff = nearest_note.find(_q(ns, "staff"))
    if staff is not None:
        ET.SubElement(note, _q(ns, "staff")).text = staff.text

    _insert_note_at_glyph_position(
        root, ns, measure, note, context, merge_into_chord=True
    )


def _insert_glyph_rest(
    root: ET.Element,
    ns: str,
    glyph: CorrectableGlyph,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> None:
    note_type = _rest_type(selected_shape)
    if note_type is None:
        raise ValueError(f"未识别休止符暂不支持该候选：{selected_shape}")
    context = _glyph_note_context(root, ns, glyph, entities, require_pitch=False)
    nearest_note = context.nearest_note
    measure = context.measure
    divisions = _measure_divisions(root, ns, measure)
    note = ET.Element(_q(ns, "note"))
    note.set("id", _unique_note_id(root, glyph.glyph_id))
    ET.SubElement(note, _q(ns, "rest"))
    ET.SubElement(note, _q(ns, "duration")).text = str(
        _rounded_duration(divisions * _duration_value(note_type))
    )
    voice = nearest_note.find(_q(ns, "voice"))
    if voice is not None:
        ET.SubElement(note, _q(ns, "voice")).text = voice.text
    ET.SubElement(note, _q(ns, "type")).text = note_type
    staff = nearest_note.find(_q(ns, "staff"))
    if staff is not None:
        ET.SubElement(note, _q(ns, "staff")).text = staff.text
    _insert_note_at_glyph_position(
        root, ns, measure, note, context, merge_into_chord=False
    )


def _glyph_note_context(
    root: ET.Element,
    ns: str,
    glyph: CorrectableGlyph,
    entities: Mapping[str, CorrectableEntity],
    *,
    require_pitch: bool,
) -> _AnchorContext:
    anchors: list[tuple[CorrectableEntity, ET.Element, ET.Element]] = []
    for entity in entities.values():
        if entity.tag != "head":
            continue
        # glyph.staff 未知时不按谱表过滤，靠 y 距离兜底（旧数据常见）
        if glyph.staff is not None and entity.staff != glyph.staff:
            continue
        if require_pitch and entity.pitch is None:
            continue
        target = _single_matching_element(root, entity)
        note = _ancestor(root, target, _q(ns, "note")) if target is not None else None
        measure = _ancestor(root, note, _q(ns, "measure")) if note is not None else None
        if note is not None and measure is not None:
            anchors.append((entity, note, measure))
    if not anchors:
        raise ValueError(f"附近没有可用于插入符号的已识别音符：{glyph.glyph_id}")

    gx, gy, gw, gh = glyph.bounds
    glyph_x = gx + gw / 2
    glyph_y = gy + gh / 2
    nearest_entity, nearest_note, measure = min(
        anchors,
        key=lambda item: (
            abs(item[0].bounds[0] + item[0].bounds[2] / 2 - glyph_x)
            + abs(item[0].bounds[1] + item[0].bounds[3] / 2 - glyph_y) * 1.5
        ),
    )

    # 同一小节内的和弦列：以组首 entity 的中心为准，followers 的 bounds 可能有位移
    groups: dict[int, tuple[ET.Element, ET.Element, CorrectableEntity]] = {}
    for entity, note, anchor_measure in anchors:
        if anchor_measure is not measure:
            continue
        group = _chord_notes(root, ns, note)
        head, tail = group[0], group[-1]
        key = id(head)
        # 优先用「组首本身对应的 entity」作为列中心
        if key not in groups or note is head:
            groups[key] = (head, tail, entity)

    columns = [
        _Column(
            center=float(entity.bounds[0]) + entity.bounds[2] / 2,
            head=head,
            tail=tail,
            voice=_xml_voice(ns, head),
            staff=_xml_staff(ns, head),
        )
        for head, tail, entity in groups.values()
    ]
    same_measure_anchors = [item for item in anchors if item[2] is measure]
    return _AnchorContext(
        anchors=anchors,
        columns=columns,
        nearest_entity=nearest_entity,
        nearest_note=nearest_note,
        measure=measure,
        glyph_x=glyph_x,
        glyph_y=glyph_y,
        tolerance=_column_tolerance(same_measure_anchors, columns),
    )


def _insert_note_at_glyph_position(
    root: ET.Element,
    ns: str,
    measure: ET.Element,
    note: ET.Element,
    context: _AnchorContext,
    *,
    merge_into_chord: bool,
) -> str:
    """把新音符放进最接近 glyph 的位置，返回实际采用的分支（便于测试与日志）。"""
    nearest_voice = _xml_voice(ns, context.nearest_note)
    nearest_staff = _xml_staff(ns, context.nearest_note)
    column = min(
        context.columns,
        key=lambda item: abs(item.center - context.glyph_x),
        default=None,
    )
    same_column = (
        column is not None and abs(column.center - context.glyph_x) <= context.tolerance
    )

    if same_column and column is not None:
        if not merge_into_chord:
            # 休止符不能进和弦组：插到组首之前，避免 follower 挂到休止符上
            measure.insert(list(measure).index(column.head), note)
            return "before_column"
        if column.voice == nearest_voice and column.staff == nearest_staff:
            if _append_chord_member(root, ns, measure, column, note):
                return "chord"

    if any(_local_name(child.tag) in {"backup", "forward"} for child in measure):
        logger.warning(
            "小节 %s 含多声部时间轴，插入的漏检符号位置可能不准确",
            measure.get("number", "?"),
        )

    right_columns = sorted(
        (
            item
            for item in context.columns
            if item.center > context.glyph_x + context.tolerance
        ),
        key=lambda item: item.center,
    )
    if right_columns:
        measure.insert(list(measure).index(right_columns[0].head), note)
        return "before_column"

    note_indices = [
        list(measure).index(item[1]) for item in context.anchors if item[2] is measure
    ]
    measure.insert(max(note_indices, default=-1) + 1, note)
    return "after_last"


def _append_chord_member(
    root: ET.Element,
    ns: str,
    measure: ET.Element,
    column: _Column,
    note: ET.Element,
) -> bool:
    """把新音符作为和弦成员追加到组尾之后。

    候选选择属于识别层修正：用户选择的音符头时值应反映到生成的简谱。
    因此遇到和弦头时值不一致时，沿用用户选择的 ``note`` 时值同步整个
    和弦列，而不是静默改回和弦头并给出误导性的“已按和弦头写入”警告。
    """
    head = column.head
    if _same_pitch_in_column(root, ns, column, note):
        logger.warning(
            "未识别音符 %s 与和弦头同音高，跳过插入",
            note.get("id", "?"),
        )
        return False

    selected_type = (note.findtext(_q(ns, "type")) or "").strip()
    if selected_type:
        # MusicXML 的和弦成员共享 onset；为让简谱文本体现用户选择的
        # 候选时值，同步这一列的所有 note。这里不做小节节拍校验，语法
        # 检查仍由右侧编辑器负责。
        for chord_note in _chord_notes(root, ns, head):
            current_type = (chord_note.findtext(_q(ns, "type")) or "").strip()
            if current_type and current_type != selected_type:
                _replace_note_type_and_duration(
                    chord_note, ns, current_type, selected_type
                )
        head_duration = (head.findtext(_q(ns, "duration")) or "").strip()
        if head_duration.isdigit() and int(head_duration) > 0:
            duration = note.find(_q(ns, "duration"))
            if duration is not None:
                duration.text = head_duration
        type_element = note.find(_q(ns, "type"))
        if type_element is None:
            type_element = ET.Element(_q(ns, "type"))
            note.append(type_element)
        type_element.text = selected_type

    _sync_note_text_from(ns, note, head, "voice", _NOTE_VOICE_SUCCESSORS)
    _sync_note_text_from(ns, note, head, "staff", _NOTE_STAFF_SUCCESSORS)

    # <chord/> 必须是 note 的第一个子元素，且紧跟组尾
    note.insert(0, ET.Element(_q(ns, "chord")))
    measure.insert(list(measure).index(column.tail) + 1, note)
    return True


_NOTE_VOICE_SUCCESSORS = {
    "type",
    "dot",
    "accidental",
    "time-modification",
    "stem",
    "notehead",
    "notehead-text",
    "staff",
    "beam",
    "notations",
    "lyric",
    "play",
    "listen",
}

_NOTE_STAFF_SUCCESSORS = {"beam", "notations", "lyric", "play", "listen"}


def _sync_note_text_from(
    ns: str,
    note: ET.Element,
    source: ET.Element,
    tag: str,
    following_tags: set[str],
) -> None:
    """让 note 的某个文本子元素与 source 一致；source 没有时移除。"""
    value = source.findtext(_q(ns, tag))
    existing = note.find(_q(ns, tag))
    if value is None:
        if existing is not None:
            note.remove(existing)
        return
    if existing is None:
        existing = ET.Element(_q(ns, tag))
        _insert_note_child(note, ns, existing, following_tags)
    existing.text = value


def _pitch_key(ns: str, note: ET.Element) -> tuple[str, str, str] | None:
    pitch = note.find(_q(ns, "pitch"))
    if pitch is None:
        return None
    step = (pitch.findtext(_q(ns, "step")) or "").strip()
    octave = (pitch.findtext(_q(ns, "octave")) or "").strip()
    if not step or not octave:
        return None
    alter = (pitch.findtext(_q(ns, "alter")) or "0").strip() or "0"
    return step, octave, alter


def _same_pitch_in_column(
    root: ET.Element,
    ns: str,
    column: _Column,
    note: ET.Element,
) -> bool:
    target = _pitch_key(ns, note)
    if target is None:
        return False
    return any(
        _pitch_key(ns, member) == target
        for member in _chord_notes(root, ns, column.head)
    )


def _shift_diatonic_pitch(step: str, octave: int, delta: int) -> tuple[str, int]:
    steps = ("C", "D", "E", "F", "G", "A", "B")
    position = octave * 7 + steps.index(step.upper()) + delta
    target_octave, target_step = divmod(position, 7)
    return steps[target_step], target_octave


def _measure_divisions(root: ET.Element, ns: str, measure: ET.Element) -> int:
    part = _ancestor(root, measure, _q(ns, "part"))
    if part is None:
        return 1
    measures = list(part.findall(_q(ns, "measure")))
    current = measures.index(measure)
    for candidate in reversed(measures[: current + 1]):
        value = candidate.findtext(f"{_q(ns, 'attributes')}/{_q(ns, 'divisions')}")
        if value:
            try:
                return max(1, int(value))
            except ValueError:
                continue
    return 1


def _unique_note_id(root: ET.Element, glyph_id: str) -> str:
    base = f"st__n-{glyph_id.replace(':', '-')}"
    existing = {element.get("id") for element in root.iter() if element.get("id")}
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _notehead_type(shape: str) -> str | None:
    if shape in {
        "NOTEHEAD_BLACK",
        "NOTEHEAD_BLACK_SMALL",
        "NOTEHEAD_CROSS",
        "NOTEHEAD_DIAMOND_FILLED",
        "NOTEHEAD_TRIANGLE_DOWN_FILLED",
        "NOTEHEAD_CIRCLE_X",
    }:
        return "quarter"
    if shape in {
        "NOTEHEAD_VOID",
        "NOTEHEAD_VOID_SMALL",
        "NOTEHEAD_CROSS_VOID",
        "NOTEHEAD_DIAMOND_VOID",
        "NOTEHEAD_TRIANGLE_DOWN_VOID",
        "NOTEHEAD_CIRCLE_X_VOID",
    }:
        return "half"
    if shape in {
        "WHOLE_NOTE",
        "WHOLE_NOTE_SMALL",
        "WHOLE_NOTE_CROSS",
        "WHOLE_NOTE_DIAMOND",
        "WHOLE_NOTE_TRIANGLE_DOWN",
        "WHOLE_NOTE_CIRCLE_X",
    }:
        return "whole"
    return None


def _replace_note_type_and_duration(
    note: ET.Element,
    ns: str,
    current_type: str | None,
    selected_type: str,
) -> None:
    type_element = note.find(_q(ns, "type"))
    if type_element is None:
        type_element = ET.Element(_q(ns, "type"))
        _insert_note_child(
            note,
            ns,
            type_element,
            {
                "dot",
                "accidental",
                "time-modification",
                "stem",
                "notehead",
                "notehead-text",
                "staff",
                "beam",
                "notations",
                "lyric",
                "play",
                "listen",
            },
        )
    type_element.text = selected_type

    duration_element = note.find(_q(ns, "duration"))
    if (
        duration_element is None
        or current_type is None
        or current_type == selected_type
    ):
        return
    try:
        duration = int(duration_element.text or "")
    except ValueError:
        return
    if duration <= 0:
        return
    ratio = _duration_value(selected_type) / _duration_value(current_type)
    duration_element.text = str(_rounded_duration(duration * ratio))


def _rounded_duration(value: Fraction) -> int:
    """Round positive durations half-up, consistently across Python versions."""
    return max(1, int(value + Fraction(1, 2)))


def _insert_note_child(
    note: ET.Element,
    ns: str,
    child: ET.Element,
    following_tags: set[str],
) -> None:
    """Insert a note child before the first schema-successor element."""
    successors = {_q(ns, tag) for tag in following_tags}
    index = next(
        (
            index
            for index, existing in enumerate(list(note))
            if existing.tag in successors
        ),
        len(note),
    )
    note.insert(index, child)


def _duration_value(note_type: str) -> Fraction:
    return {
        "whole": Fraction(4),
        "half": Fraction(2),
        "quarter": Fraction(1),
        "eighth": Fraction(1, 2),
        "16th": Fraction(1, 4),
        "32nd": Fraction(1, 8),
        "64th": Fraction(1, 16),
        "128th": Fraction(1, 32),
        "breve": Fraction(8),
        "long": Fraction(16),
    }[note_type]


def _rest_type(shape: str) -> str | None:
    name = shape.upper()
    for prefix, value in (
        ("ONE_128TH_REST", "128th"),
        ("ONE_64TH_REST", "64th"),
        ("ONE_32ND_REST", "32nd"),
        ("ONE_16TH_REST", "16th"),
        ("EIGHTH_REST", "eighth"),
        ("QUARTER_REST", "quarter"),
        ("HALF_REST", "half"),
        ("WHOLE_REST", "whole"),
        ("BREVE_REST", "breve"),
        ("LONG_REST", "long"),
        ("HW_REST", "half"),
    ):
        if name == prefix:
            return value
    return None


def _replace_rest_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    note_type = _rest_type(selected_shape)
    if note_type is None:
        raise ValueError(f"暂不支持休止符候选：{selected_shape}")
    note = _ancestor(root, target, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到休止符")
    current_type = note.findtext(_q(ns, "type")) or _rest_type(entity.shape)
    rest = note.find(_q(ns, "rest"))
    if rest is None:
        rest = ET.Element(_q(ns, "rest"))
        note.insert(0, rest)
    _replace_note_type_and_duration(note, ns, current_type, note_type)


def _alter_values(shape: str) -> tuple[str, str] | None:
    return {
        "SHARP": ("1", "sharp"),
        "FLAT": ("-1", "flat"),
        "NATURAL": ("0", "natural"),
        "DOUBLE_SHARP": ("2", "double-sharp"),
        "DOUBLE_FLAT": ("-2", "flat-flat"),
        "QUARTER_SHARP": ("0.5", "quarter-sharp"),
        "QUARTER_FLAT": ("-0.5", "quarter-flat"),
        "THREE_QUARTERS_SHARP": ("1.5", "three-quarters-sharp"),
        "THREE_QUARTERS_FLAT": ("-1.5", "three-quarters-flat"),
    }.get(shape)


def _replace_alter_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    values = _alter_values(selected_shape)
    if values is None:
        raise ValueError(f"暂不支持变音记号候选：{selected_shape}")
    note = _ancestor(root, target, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到音符")
    pitch = note.find(_q(ns, "pitch"))
    if pitch is None:
        raise ValueError(f"标记 {entity.source_id} 对应的音符没有音高")
    alter = pitch.find(_q(ns, "alter"))
    if alter is None:
        alter = ET.Element(_q(ns, "alter"))
        octave = pitch.find(_q(ns, "octave"))
        pitch.insert(
            list(pitch).index(octave) if octave is not None else len(pitch), alter
        )
    alter.text = values[0]
    accidental = note.find(_q(ns, "accidental"))
    if accidental is None:
        accidental = ET.Element(_q(ns, "accidental"))
        _insert_note_child(
            note,
            ns,
            accidental,
            {
                "time-modification",
                "stem",
                "notehead",
                "notehead-text",
                "staff",
                "beam",
                "notations",
                "lyric",
                "play",
                "listen",
            },
        )
    accidental.text = values[1]


def _replace_clef_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element | None,
    entity: CorrectableEntity,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> bool:
    if target is not None and _local_name(target.tag) != "clef":
        target = _ancestor(root, target, _q(ns, "clef"))
    properties = _clef_properties(selected_shape)
    if properties is None:
        raise ValueError(f"暂不支持谱号候选：{selected_shape}")
    if target is None:
        anchor = _nearest_clef_anchor(root, ns, entity, entities)
        if anchor is None:
            logger.warning(
                "跳过无法定位的谱号候选 %s：没有同谱表音符锚点", entity.source_id
            )
            return False
        old_properties = _clef_properties(entity.shape)
        if old_properties is None:
            raise ValueError(f"无法读取原谱号：{entity.shape}")
        xml_staff_number = anchor.findtext(_q(ns, "staff"), "1").strip()
        target = _insert_clef(root, ns, anchor, xml_staff_number, *properties)
        old_sign, old_line, old_octave = old_properties
    else:
        old_sign, old_line, old_octave = _clef_value(target, ns)
    measure = _ancestor(root, target, _q(ns, "measure"))
    part = _ancestor(root, target, _q(ns, "part"))
    if measure is None or part is None:
        raise ValueError(f"谱号 {entity.source_id} 缺少 MusicXML 上下文")
    new_sign, new_line, new_octave = properties
    target.find(_q(ns, "sign")).text = new_sign
    target.find(_q(ns, "line")).text = str(new_line)
    octave_element = target.find(_q(ns, "clef-octave-change"))
    if new_octave:
        if octave_element is None:
            octave_element = ET.SubElement(target, _q(ns, "clef-octave-change"))
        octave_element.text = str(new_octave)
    elif octave_element is not None:
        target.remove(octave_element)
    if (old_sign, old_line, old_octave) != (new_sign, new_line, new_octave):
        staff_number = target.get("number", "1")
        next_system = _next_system_measure(part, measure, ns)
        if next_system is not None and not _measure_has_clef(
            next_system, ns, staff_number
        ):
            _insert_clef(
                root,
                ns,
                next_system,
                staff_number,
                old_sign,
                old_line,
                old_octave,
            )
        _transform_notes_until_next_clef(
            part,
            measure,
            ns,
            staff_number,
            old_sign,
            old_line,
            new_sign,
            new_line,
            old_octave,
            new_octave,
        )
    return True


def _nearest_clef_anchor(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    entities: Mapping[str, CorrectableEntity],
) -> ET.Element | None:
    clef_x = entity.bounds[0] + entity.bounds[2] / 2
    clef_y = entity.bounds[1] + entity.bounds[3] / 2
    anchors: list[tuple[float, ET.Element]] = []
    for candidate in entities.values():
        if candidate.tag != "head" or (
            entity.staff and candidate.staff != entity.staff
        ):
            continue
        note = _target_note(root, ns, candidate)
        if note is None:
            continue
        note_x = candidate.bounds[0] + candidate.bounds[2] / 2
        note_y = candidate.bounds[1] + candidate.bounds[3] / 2
        horizontal = note_x - clef_x
        if horizontal < 0 or abs(note_y - clef_y) > 2 * max(1, entity.bounds[3]):
            continue
        anchors.append((abs(note_y - clef_y) * 3 + horizontal * 0.1, note))
    return min(anchors, key=lambda item: item[0])[1] if anchors else None


def _insert_clef(
    root: ET.Element,
    ns: str,
    anchor: ET.Element,
    staff_number: str,
    sign: str,
    line: int,
    octave_change: int,
) -> ET.Element:
    measure = (
        anchor
        if _local_name(anchor.tag) == "measure"
        else _ancestor(root, anchor, _q(ns, "measure"))
    )
    if measure is None:
        raise ValueError("谱号锚点缺少小节")
    attributes = measure.find(_q(ns, "attributes"))
    if attributes is None:
        attributes = ET.Element(_q(ns, "attributes"))
        children = list(measure)
        first_music = next(
            (
                index
                for index, child in enumerate(children)
                if _local_name(child.tag) in {"note", "backup", "forward"}
            ),
            len(children),
        )
        measure.insert(first_music, attributes)
    clef = ET.Element(_q(ns, "clef"), {"number": staff_number})
    ET.SubElement(clef, _q(ns, "sign")).text = sign
    ET.SubElement(clef, _q(ns, "line")).text = str(line)
    if octave_change:
        ET.SubElement(clef, _q(ns, "clef-octave-change")).text = str(octave_change)
    attributes.append(clef)
    return clef


def _next_system_measure(
    part: ET.Element,
    current_measure: ET.Element,
    ns: str,
) -> ET.Element | None:
    measures = list(part.findall(_q(ns, "measure")))
    try:
        index = measures.index(current_measure)
    except ValueError:
        return None
    return next(
        (
            measure
            for measure in measures[index + 1 :]
            if any(
                print_element.get("new-system") == "yes"
                for print_element in measure.findall(_q(ns, "print"))
            )
        ),
        None,
    )


def _measure_has_clef(measure: ET.Element, ns: str, staff_number: str) -> bool:
    attributes = measure.find(_q(ns, "attributes"))
    return attributes is not None and any(
        clef.get("number", "1") == staff_number
        for clef in attributes.findall(_q(ns, "clef"))
    )


def _clef_properties(shape: str) -> tuple[str, int, int] | None:
    name = shape.upper()
    if "PERCUSSION_CLEF" in name:
        sign, line = "percussion", 2
    elif "G_CLEF" in name:
        sign, line = "G", 2
    elif "F_CLEF" in name:
        sign, line = "F", 4
    elif "C_CLEF" in name:
        sign, line = "C", 3
    else:
        return None
    octave = 1 if name.endswith("8VA") else -1 if name.endswith("8VB") else 0
    return sign, line, octave


def _replace_key_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    if _local_name(target.tag) != "key":
        target = next(
            (node for node in target.iter() if _local_name(node.tag) == "key"),
            None,
        )
    name = selected_shape.upper()
    if target is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到调号")
    if name == "KEY_CANCEL":
        fifths = 0
    elif name.startswith("KEY_SHARP_"):
        fifths = int(name.rsplit("_", 1)[1])
    elif name.startswith("KEY_FLAT_"):
        fifths = -int(name.rsplit("_", 1)[1])
    else:
        raise ValueError(f"暂不支持调号候选：{selected_shape}")
    fifths_element = target.find(_q(ns, "fifths"))
    if fifths_element is None:
        fifths_element = ET.Element(_q(ns, "fifths"))
        target.insert(0, fifths_element)
    fifths_element.text = str(fifths)


def _replace_time_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    if _local_name(target.tag) != "time":
        target = _ancestor(root, target, _q(ns, "time"))
    if target is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到拍号")
    values = {
        "COMMON_TIME": (4, 4, "common"),
        "CUT_TIME": (2, 2, "cut"),
        "TIME_FOUR_FOUR": (4, 4, None),
        "TIME_TWO_TWO": (2, 2, None),
        "TIME_TWO_FOUR": (2, 4, None),
        "TIME_THREE_FOUR": (3, 4, None),
        "TIME_FIVE_FOUR": (5, 4, None),
        "TIME_SIX_FOUR": (6, 4, None),
        "TIME_THREE_EIGHT": (3, 8, None),
        "TIME_SIX_EIGHT": (6, 8, None),
        "TIME_NINE_EIGHT": (9, 8, None),
        "TIME_TWELVE_EIGHT": (12, 8, None),
    }
    value = values.get(selected_shape.upper())
    if value is None:
        raise ValueError(f"暂不支持拍号候选：{selected_shape}")
    beats, beat_type, symbol = value
    for child in list(target):
        target.remove(child)
    target.attrib.pop("symbol", None)
    if symbol:
        target.set("symbol", symbol)
    ET.SubElement(target, _q(ns, "beats")).text = str(beats)
    ET.SubElement(target, _q(ns, "beat-type")).text = str(beat_type)


def _replace_dynamic_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
) -> None:
    name = selected_shape.upper()
    dynamic_names = {
        "DYNAMICS_PPP": "ppp",
        "DYNAMICS_PP": "pp",
        "DYNAMICS_P": "p",
        "DYNAMICS_MP": "mp",
        "DYNAMICS_MF": "mf",
        "DYNAMICS_F": "f",
        "DYNAMICS_FF": "ff",
        "DYNAMICS_FFF": "fff",
        "DYNAMICS_FP": "fp",
        "DYNAMICS_FZ": "fz",
        "DYNAMICS_SF": "sf",
        "DYNAMICS_SFZ": "sfz",
        "SF": "sf",
        "SFZ": "sfz",
    }
    tag = dynamic_names.get(name)
    if tag is None:
        raise ValueError(f"暂不支持力度记号候选：{selected_shape}")
    direction = (
        target
        if _local_name(target.tag) == "direction"
        else _ancestor(root, target, _q(ns, "direction"))
    )
    if direction is None:
        note = _ancestor(root, target, _q(ns, "note"))
        measure = _ancestor(root, note, _q(ns, "measure")) if note is not None else None
        if measure is None:
            raise ValueError(f"标记 {entity.source_id} 未定位到力度记号容器")
        direction = ET.Element(_q(ns, "direction"))
        measure.insert(list(measure).index(note), direction)
    for direction_type in list(direction.findall(_q(ns, "direction-type"))):
        for dynamics in list(direction_type.findall(_q(ns, "dynamics"))):
            direction_type.remove(dynamics)
        if not list(direction_type):
            direction.remove(direction_type)
    direction_type = ET.Element(_q(ns, "direction-type"))
    children = list(direction)
    insert_at = next(
        (
            index
            for index, child in enumerate(children)
            if _local_name(child.tag) != "direction-type"
        ),
        len(children),
    )
    direction.insert(insert_at, direction_type)
    dynamics = ET.SubElement(direction_type, _q(ns, "dynamics"))
    ET.SubElement(dynamics, _q(ns, tag))


def _replace_wedge_candidate(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
) -> bool:
    wedge_type = {"CRESCENDO": "crescendo", "DIMINUENDO": "diminuendo"}.get(
        selected_shape.upper()
    )
    if wedge_type is None:
        raise ValueError(f"暂不支持渐强/渐弱候选：{selected_shape}")
    directions = [
        item
        for item in _matching_elements(root, entity)
        if _local_name(item.tag) == "direction"
    ]
    wedges = [
        wedge for direction in directions for wedge in direction.iter(_q(ns, "wedge"))
    ]
    if not wedges:
        logger.warning("跳过无法定位的力度渐变候选 %s", entity.source_id)
        return False
    for wedge in wedges:
        if wedge.get("type") != "stop":
            wedge.set("type", wedge_type)
    return True


def _replace_pedal_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element | None,
    entity: CorrectableEntity,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> bool:
    pedal_type = {"PEDAL_MARK": "start", "PEDAL_UP_MARK": "stop"}.get(
        selected_shape.upper()
    )
    if pedal_type is None:
        raise ValueError(f"暂不支持踏板候选：{selected_shape}")
    direction = (
        target
        if target is not None and _local_name(target.tag) == "direction"
        else _ancestor(root, target, _q(ns, "direction"))
        if target is not None
        else None
    )
    pedal = (
        next((item for item in direction.iter(_q(ns, "pedal"))), None)
        if direction is not None
        else None
    )
    if pedal is None:
        return _insert_pedal_candidate(root, ns, entity, selected_shape, entities)
    pedal.set("type", pedal_type)
    sound = direction.find(_q(ns, "sound"))
    if sound is not None:
        sound.set("damper-pedal", "yes" if pedal_type == "start" else "no")
    return True


def _insert_pedal_candidate(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
    selected_shape: str,
    entities: Mapping[str, CorrectableEntity],
) -> bool:
    """Insert a pedal direction near its score position when Audiveris omitted it.

    Some Audiveris scores retain a pedal Inter in the OMR graph and export it in
    the link map, but omit its MusicXML direction. Anchor the replacement to the
    nearest mapped note on the same staff so the selected recognition reaches
    the regenerated score instead of silently becoming a no-op.
    """
    pedal_type = {"PEDAL_MARK": "start", "PEDAL_UP_MARK": "stop"}.get(
        selected_shape.upper()
    )
    if pedal_type is None:
        raise ValueError(f"暂不支持踏板候选：{selected_shape}")

    anchors: list[tuple[float, ET.Element, ET.Element]] = []
    center_x = entity.bounds[0] + entity.bounds[2] / 2
    for source_entity in entities.values():
        if source_entity.tag != "head" or (
            entity.staff and source_entity.staff != entity.staff
        ):
            continue
        for target_note in _matching_notes(root, ns, source_entity):
            measure = _ancestor(root, target_note, _q(ns, "measure"))
            if measure is not None:
                note_x = source_entity.bounds[0] + source_entity.bounds[2] / 2
                anchors.append((abs(note_x - center_x), target_note, measure))

    if not anchors:
        logger.warning(
            "跳过无法定位的踏板候选 %s：没有同谱表音符锚点", entity.source_id
        )
        return False
    _, note, measure = min(anchors, key=lambda item: item[0])
    direction = ET.Element(_q(ns, "direction"))
    direction_type = ET.SubElement(direction, _q(ns, "direction-type"))
    pedal = ET.SubElement(direction_type, _q(ns, "pedal"), {"type": pedal_type})
    pedal.set("line", "no")
    sound = ET.SubElement(direction, _q(ns, "sound"))
    sound.set("damper-pedal", "yes" if pedal_type == "start" else "no")
    measure.insert(list(measure).index(note), direction)
    return True


def _replace_notation_candidate(
    root: ET.Element,
    ns: str,
    target: ET.Element,
    entity: CorrectableEntity,
    selected_shape: str,
    family: str,
) -> None:
    note = _ancestor(root, target, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到音符")
    notations = note.find(_q(ns, "notations"))
    if notations is None:
        notations = ET.SubElement(note, _q(ns, "notations"))
    if family == "fermata":
        for old in list(notations.findall(_q(ns, "fermata"))):
            notations.remove(old)
        fermata = ET.SubElement(notations, _q(ns, "fermata"))
        fermata.set("type", "inverted" if "BELOW" in selected_shape else "upright")
        return

    if family == "arpeggiato":
        for old in list(notations.findall(_q(ns, "arpeggiate"))):
            notations.remove(old)
        if selected_shape.upper() != "ARPEGGIATO":
            raise ValueError(f"暂不支持琶音候选：{selected_shape}")
        ET.SubElement(notations, _q(ns, "arpeggiate"))
        return

    if family == "pause":
        parent_tag = "articulations"
        mapping = {"BREATH_MARK": "breath-mark", "CAESURA": "caesura"}
        tag = mapping.get(selected_shape.upper())
        if tag is None:
            raise ValueError(f"暂不支持停顿记号候选：{selected_shape}")
        container = notations.find(_q(ns, parent_tag))
        if container is None:
            container = ET.SubElement(notations, _q(ns, parent_tag))
        for old_name in ("breath-mark", "caesura"):
            for child in list(container.findall(_q(ns, old_name))):
                container.remove(child)
        ET.SubElement(container, _q(ns, tag))
        return

    if family == "articulation":
        parent_tag = "articulations"
        mapping = {
            "STACCATO": "staccato",
            "STACCATO_BELOW": "staccato",
            "STACCATISSIMO": "staccatissimo",
            "ACCENT": "accent",
            "STRONG_ACCENT": "strong-accent",
            "TENUTO": "tenuto",
            "MARCATO": "strong-accent",
            "MARCATO_BELOW": "strong-accent",
        }
    else:
        parent_tag = "ornaments"
        mapping = {
            "TR": "trill-mark",
            "MORDENT": "mordent",
            "MORDENT_INVERTED": "inverted-mordent",
            "TURN": "turn",
            "TURN_INVERTED": "inverted-turn",
            "TURN_UP": "turn",
            "TURN_SLASH": "turn",
        }
    tag = mapping.get(selected_shape.upper())
    if tag is None:
        raise ValueError(f"暂不支持记号候选：{selected_shape}")
    container = notations.find(_q(ns, parent_tag))
    if container is None:
        container = ET.SubElement(notations, _q(ns, parent_tag))
    # Replace only the articulation/ornament represented by this entity. A note
    # may legitimately carry several marks from the same container (for example
    # accent + staccato), so clearing the container would delete unrelated data.
    previous_tag = mapping.get(entity.shape.upper())
    if previous_tag is not None:
        previous = container.find(_q(ns, previous_tag))
        if previous is not None:
            container.remove(previous)
    ET.SubElement(container, _q(ns, tag))


def _musicxml_notehead_style(shape: str) -> str:
    if "DIAMOND" in shape:
        return "diamond"
    if "CROSS" in shape or "CIRCLE_X" in shape:
        return "x"
    if "TRIANGLE_DOWN" in shape:
        return "triangle-down"
    return "normal"


def _detect_namespace(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[0].lstrip("{")
    return ""


def _q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}" if ns else name


def _serialize(root: ET.Element, ns: str) -> str:
    if ns:
        ET.register_namespace("", ns)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


def _locator_matches(element_id: str, locator: str) -> bool:
    """Match one complete provenance segment, never a numeric id prefix.

    Audiveris note ids join sources with ``__`` (for example
    ``st__n-s1-i1__a-s1-i2``). Slurs use ``ss``/``se`` in MusicXML while the
    link map uses the common ``s`` role, and wedges share one locator between
    their ``-start`` and ``-stop`` directions.
    """
    if not element_id or not locator:
        return False
    segments = element_id.split("__")
    if locator in segments:
        return True
    if locator.startswith("wg-") and any(
        segment in {f"{locator}-start", f"{locator}-stop"} for segment in segments
    ):
        return True
    if locator.startswith(("s-", "t-")):
        suffix = locator[2:]
        prefixes = ("s", "t") if locator.startswith("s-") else ("t",)
        return any(
            f"{prefix}{side}-{suffix}" in segments
            for prefix in prefixes
            for side in ("s", "e")
        )
    return False


def _matching_elements(root: ET.Element, entity: CorrectableEntity) -> list[ET.Element]:
    return [
        element
        for element in root.iter()
        if _locator_matches(
            element.get(entity.musicxml_attribute, ""), entity.musicxml_locator
        )
    ]


def _single_matching_element(
    root: ET.Element, entity: CorrectableEntity
) -> ET.Element | None:
    matches = _matching_elements(root, entity)
    if not matches:
        # Audiveris 的 score-link-map 偶尔为结构元素引用了 MusicXML 未导出的 id
        # （谱号/调号通常只给首个标注 id）。这种幻影引用没有可删除的元素，
        # 跳过而非中断整批修正；真正的歧义（>1）仍需报错以免删错。
        logger.warning("跳过无法定位的标记 %s：MusicXML 中无对应元素", entity.source_id)
        return None
    if len(matches) > 1:
        raise ValueError(
            f"标记 {entity.source_id} 的 MusicXML 定位结果不唯一：{len(matches)}"
        )
    return matches[0]


def _ancestor(
    root: ET.Element,
    element: ET.Element,
    tag: str,
) -> ET.Element | None:
    for candidate in root.iter(tag):
        if candidate is element or element in candidate.iter():
            return candidate
    return None


def _parent(root: ET.Element, child: ET.Element) -> ET.Element | None:
    for candidate in root.iter():
        if child in candidate:
            return candidate
    return None


def _target_note(
    root: ET.Element, ns: str, entity: CorrectableEntity
) -> ET.Element | None:
    matched = _single_matching_element(root, entity)
    if matched is None:
        return None
    note = _ancestor(root, matched, _q(ns, "note"))
    if note is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到音符")
    return note


def _replace_note_head_with_rest(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
) -> None:
    note = _target_note(root, ns, entity)
    if note is None:
        return
    measure = _parent(root, note)
    if measure is None:
        raise ValueError(f"音符 {entity.source_id} 缺少小节容器")
    siblings = list(measure)
    index = siblings.index(note)
    next_note = siblings[index + 1] if index + 1 < len(siblings) else None
    is_chord_member = note.find(_q(ns, "chord")) is not None
    has_chord_follower = (
        next_note is not None
        and next_note.tag == _q(ns, "note")
        and next_note.find(_q(ns, "chord")) is not None
    )
    if is_chord_member:
        measure.remove(note)
        return
    if has_chord_follower:
        chord_marker = next_note.find(_q(ns, "chord"))
        if chord_marker is not None:
            next_note.remove(chord_marker)
        measure.remove(note)
        return

    pitch = note.find(_q(ns, "pitch"))
    if pitch is None:
        raise ValueError(f"标记 {entity.source_id} 对应的音符没有音高")
    pitch_index = list(note).index(pitch)
    note.remove(pitch)
    for child_name in ("accidental", "tie", "notations", "beam", "stem"):
        for child in list(note.findall(_q(ns, child_name))):
            note.remove(child)
    note.insert(pitch_index, ET.Element(_q(ns, "rest")))
    note.set("print-object", "no")


def _remove_note(root: ET.Element, ns: str, entity: CorrectableEntity) -> None:
    note = _target_note(root, ns, entity)
    if note is None:
        return
    parent = _parent(root, note)
    if parent is None:
        raise ValueError(f"音符 {entity.source_id} 缺少小节容器")
    parent.remove(note)


def _remove_accidental(root: ET.Element, ns: str, entity: CorrectableEntity) -> None:
    note = _target_note(root, ns, entity)
    if note is None:
        return
    accidental = note.find(_q(ns, "accidental"))
    if accidental is not None:
        note.remove(accidental)
    pitch = note.find(_q(ns, "pitch"))
    alter = pitch.find(_q(ns, "alter")) if pitch is not None else None
    if pitch is not None and alter is not None:
        pitch.remove(alter)


def _remove_notation_mark(root: ET.Element, ns: str, entity: CorrectableEntity) -> None:
    """Remove only the MusicXML mark represented by an OMR entity.

    Source ids for note-attached marks are carried by their enclosing note;
    direction marks carry them on the direction itself. Keep sibling marks,
    note content, and direction text intact.
    """
    tag = entity.tag
    targets = _matching_elements(root, entity)

    if tag in {"slur", "tie", "tuplet"}:
        notes = _matching_notes(root, ns, entity)
        if tag == "tuplet":
            _remove_tuplet_marks(root, ns, notes)
            return
        locator_suffix = entity.musicxml_locator[2:]
        is_tie = tag == "tie" or (
            tag == "slur"
            and any(
                segment in {f"ts-{locator_suffix}", f"te-{locator_suffix}"}
                for target in targets
                for segment in target.get(entity.musicxml_attribute, "").split("__")
            )
        )
        names = {
            "slur": ("tie", "tied") if is_tie else ("slur",),
            "tie": ("tie", "tied"),
            "tuplet": ("tuplet",),
        }[tag]
        changed = False
        for note in notes:
            notations = note.find(_q(ns, "notations"))
            for container in (note, notations) if notations is not None else (note,):
                for name in names:
                    for mark in list(container.findall(_q(ns, name))):
                        container.remove(mark)
                        changed = True
        if not changed:
            logger.warning("跳过无法定位的%s标记：%s", tag, entity.source_id)
        return

    if tag == "augmentation-dot":
        notes = _matching_notes(root, ns, entity)
        for note in notes:
            dot = note.find(_q(ns, "dot"))
            if dot is not None:
                note.remove(dot)
                _rescale_duration_after_dot_removal(root, ns, note)
                return
        logger.warning("跳过无法定位的附点标记：%s", entity.source_id)
        return

    # Map Audiveris Inter types to the MusicXML leaf that encodes the same mark.
    shape = entity.shape.upper()
    shape_to_leaf = {
        "STACCATO": (("articulations",), "staccato"),
        "STACCATO_BELOW": (("articulations",), "staccato"),
        "STACCATISSIMO": (("articulations",), "staccatissimo"),
        "ACCENT": (("articulations",), "accent"),
        "STRONG_ACCENT": (("articulations",), "strong-accent"),
        "TENUTO": (("articulations",), "tenuto"),
        "MARCATO": (("articulations",), "strong-accent"),
        "MARCATO_BELOW": (("articulations",), "strong-accent"),
        "TR": (("ornaments",), "trill-mark"),
        "MORDENT": (("ornaments",), "mordent"),
        "MORDENT_INVERTED": (("ornaments",), "inverted-mordent"),
        "TURN": (("ornaments",), "turn"),
        "TURN_INVERTED": (("ornaments",), "inverted-turn"),
        "TURN_UP": (("ornaments",), "turn"),
        "TURN_SLASH": (("ornaments",), "turn"),
        "BREATH_MARK": (("articulations",), "breath-mark"),
        "CAESURA": (("articulations",), "caesura"),
        "FERMATA": (("notations",), "fermata"),
        "FERMATA_BELOW": (("notations",), "fermata"),
        "ARPEGGIATO": (("notations",), "arpeggiate"),
        "BOW_UP": (("technical",), "up-bow"),
        "BOW_DOWN": (("technical",), "down-bow"),
        "PLUCK_P": (("technical",), "pluck"),
        "PLUCK_I": (("technical",), "pluck"),
        "PLUCK_M": (("technical",), "pluck"),
        "PLUCK_A": (("technical",), "pluck"),
        "PEDAL_MARK": (("direction-type",), "pedal"),
        "PEDAL_UP_MARK": (("direction-type",), "pedal"),
    }
    if tag in {"dynamics", "dynamic"}:
        containers, leaf = ("direction-type",), "dynamics"
    elif tag == "fingering":
        containers, leaf = ("technical",), "fingering"
    elif tag == "plucking":
        containers, leaf = ("technical",), "pluck"
    elif tag == "wedge":
        containers, leaf = ("direction-type",), "wedge"
    elif tag == "pedal":
        containers, leaf = ("direction-type",), "pedal"
    elif tag == "fermata":
        containers, leaf = ("notations",), "fermata"
    elif tag in {"pause", "breath-mark", "caesura"}:
        containers = ("articulations",)
        leaf = "caesura" if "CAESURA" in shape else "breath-mark"
    elif tag == "arpeggiato":
        containers, leaf = ("notations",), "arpeggiate"
    else:
        containers, leaf = shape_to_leaf.get(shape, ((), ""))
        if not containers:
            logger.warning("暂不支持删除%s标记：%s", tag, entity.source_id)
            return

    changed = False
    for target in targets:
        # For direction-based entities target is normally the direction itself;
        # for note-based marks it is the note id or a nested element.
        owners = [target]
        note = _ancestor(root, target, _q(ns, "note"))
        direction = _ancestor(root, target, _q(ns, "direction"))
        if note is not None:
            if tag in {"dynamics", "dynamic"}:
                dynamic_direction = _direction_for_note(root, ns, note)
                owners = [dynamic_direction] if dynamic_direction is not None else []
            else:
                owners = [note]
        elif direction is not None:
            owners = [direction]
        for owner in owners:
            for container_name in containers:
                containers_found = (
                    [owner]
                    if _local_name(owner.tag) == container_name
                    else list(owner.iter(_q(ns, container_name)))
                )
                for container in containers_found:
                    for mark in list(container.findall(_q(ns, leaf))):
                        container.remove(mark)
                        changed = True
            if tag in {"dynamics", "dynamic"}:
                for direction_type in list(owner.findall(_q(ns, "direction-type"))):
                    if not list(direction_type):
                        owner.remove(direction_type)
                if _local_name(owner.tag) == "direction":
                    sound = owner.find(_q(ns, "sound"))
                    if sound is not None:
                        sound.attrib.pop("dynamics", None)
                        if not sound.attrib:
                            owner.remove(sound)
            if tag == "pedal" and _local_name(owner.tag) == "direction":
                sound = owner.find(_q(ns, "sound"))
                if sound is not None:
                    sound.attrib.pop("damper-pedal", None)
                    if not sound.attrib:
                        owner.remove(sound)
            if tag == "wedge" and _local_name(owner.tag) == "direction":
                sound = owner.find(_q(ns, "sound"))
                if sound is not None:
                    sound.attrib.pop("dynamics", None)
                    if not sound.attrib:
                        owner.remove(sound)
    if not changed:
        logger.warning("跳过无法定位的%s标记：%s", tag, entity.source_id)


def _direction_for_note(
    root: ET.Element,
    ns: str,
    note: ET.Element,
) -> ET.Element | None:
    """Resolve Audiveris' id-less dynamic direction from its linked note.

    Audiveris stores the dynamic Inter source id on the note provenance, but
    its current MusicXML exporter does not set an id on the generated
    ``<direction>``. The direction is emitted immediately before its linked
    note, so select the nearest preceding direction that actually contains a
    ``<dynamics>`` element.
    """
    measure = _ancestor(root, note, _q(ns, "measure"))
    if measure is None:
        return None
    children = list(measure)
    try:
        note_index = children.index(note)
    except ValueError:
        return None
    for sibling in reversed(children[:note_index]):
        if sibling.tag == _q(ns, "direction") and sibling.find(
            f"{_q(ns, 'direction-type')}/{_q(ns, 'dynamics')}"
        ) is not None:
            return sibling
    return None


def _rescale_duration_after_dot_removal(
    root: ET.Element,
    ns: str,
    note: ET.Element,
) -> None:
    """Keep MusicXML duration consistent after removing a rhythm dot.

    Audiveris writes the expanded duration (for example ``3`` for a dotted
    quarter with divisions ``2``). Removing only ``<dot/>`` would therefore
    still make the Jianpu parser infer a dotted value from the duration.
    Rescale the whole chord column from the old dot multiplier to the new one.
    """
    old_dots = len(note.findall(_q(ns, "dot"))) + 1
    old_multiplier = Fraction(2, 1) - Fraction(1, 2**old_dots)
    new_dots = max(0, old_dots - 1)
    new_multiplier = (
        Fraction(1, 1) if new_dots == 0 else Fraction(2, 1) - Fraction(1, 2**new_dots)
    )
    if old_multiplier == 0 or new_multiplier == old_multiplier:
        return
    for chord_note in _chord_notes(root, ns, note):
        duration = chord_note.find(_q(ns, "duration"))
        if duration is None:
            continue
        try:
            current = Fraction(int((duration.text or "0").strip()), 1)
        except ValueError:
            continue
        base = current / old_multiplier
        updated = base * new_multiplier
        duration.text = str(max(1, round(float(updated))))


def _remove_tuplet_marks(
    root: ET.Element,
    ns: str,
    matched_notes: list[ET.Element],
) -> None:
    """Remove a tuplet's printed notation and timing modifier as one unit."""
    changed = False
    for note in matched_notes:
        notations = note.find(_q(ns, "notations"))
        if notations is not None:
            for mark in list(notations.findall(_q(ns, "tuplet"))):
                notations.remove(mark)
                changed = True

    measures: list[ET.Element] = []
    for note in matched_notes:
        measure = _ancestor(root, note, _q(ns, "measure"))
        if measure is not None and measure not in measures:
            measures.append(measure)
    for measure in measures:
        notes = list(measure.findall(_q(ns, "note")))
        indices = [index for index, note in enumerate(notes) if note in matched_notes]
        if not indices:
            continue
        reference = matched_notes[0]
        voice = reference.findtext(_q(ns, "voice"))
        staff = reference.findtext(_q(ns, "staff"))
        for note in notes[min(indices) : max(indices) + 1]:
            if note.findtext(_q(ns, "voice")) != voice:
                continue
            if note.findtext(_q(ns, "staff")) != staff:
                continue
            modifier = note.find(_q(ns, "time-modification"))
            if modifier is not None:
                note.remove(modifier)
                changed = True
    if not changed:
        logger.warning("跳过无法定位的连音标记")


def _delete_attribute_element(
    root: ET.Element,
    entity: CorrectableEntity,
    expected_local_name: str,
) -> None:
    target = _single_matching_element(root, entity)
    if target is None:
        return
    if _local_name(target.tag) != expected_local_name:
        target = next(
            (
                candidate
                for candidate in target.iter()
                if _local_name(candidate.tag) == expected_local_name
            ),
            None,
        )
    if target is None or _local_name(target.tag) != expected_local_name:
        raise ValueError(f"标记 {entity.source_id} 未定位到 {expected_local_name}")
    parent = _parent(root, target)
    if parent is None:
        raise ValueError(f"标记 {entity.source_id} 缺少 MusicXML 父节点")
    parent.remove(target)


def _delete_clef_with_pitch_transform(
    root: ET.Element,
    ns: str,
    entity: CorrectableEntity,
) -> None:
    target = _single_matching_element(root, entity)
    if target is None:
        return
    if _local_name(target.tag) != "clef":
        target = _ancestor(root, target, _q(ns, "clef"))
    if target is None:
        raise ValueError(f"标记 {entity.source_id} 未定位到谱号")

    attributes = _parent(root, target)
    measure = _ancestor(root, target, _q(ns, "measure"))
    part = _ancestor(root, target, _q(ns, "part"))
    if attributes is None or measure is None or part is None:
        raise ValueError(f"谱号 {entity.source_id} 缺少 MusicXML 上下文")

    old_sign, old_line, old_octave_change = _clef_value(target, ns)
    staff_number = target.get("number", "1")
    new_sign, new_line, new_octave_change = _previous_clef(
        part, measure, target, ns, staff_number
    )
    attributes.remove(target)
    if (old_sign, old_line, old_octave_change) != (
        new_sign,
        new_line,
        new_octave_change,
    ):
        _transform_notes_until_next_clef(
            part,
            measure,
            ns,
            staff_number,
            old_sign,
            old_line,
            new_sign,
            new_line,
            old_octave_change,
            new_octave_change,
        )


def _clef_value(clef: ET.Element, ns: str) -> tuple[str, int, int]:
    sign = clef.findtext(_q(ns, "sign"), "G").strip()
    line_text = clef.findtext(_q(ns, "line"), "2").strip()
    octave_change = clef.findtext(_q(ns, "clef-octave-change"), "0").strip()
    return sign, int(line_text), int(octave_change)


def _previous_clef(
    part: ET.Element,
    target_measure: ET.Element,
    target: ET.Element,
    ns: str,
    staff_number: str,
) -> tuple[str, int, int]:
    previous: tuple[str, int, int] = ("G", 2, 0)
    for measure in part.findall(_q(ns, "measure")):
        attributes = measure.find(_q(ns, "attributes"))
        if attributes is not None:
            for clef in attributes.findall(_q(ns, "clef")):
                if clef is target:
                    return previous
                if clef.get("number", "1") == staff_number:
                    previous = _clef_value(clef, ns)
        if measure is target_measure:
            return previous
    return previous


def _transform_notes_until_next_clef(
    part: ET.Element,
    start_measure: ET.Element,
    ns: str,
    staff_number: str,
    old_sign: str,
    old_line: int,
    new_sign: str,
    new_line: int,
    old_octave_change: int,
    new_octave_change: int,
) -> None:
    active = False
    for measure in part.findall(_q(ns, "measure")):
        if measure is start_measure:
            active = True
        if not active:
            continue
        if measure is not start_measure:
            attributes = measure.find(_q(ns, "attributes"))
            if attributes is not None and any(
                clef.get("number", "1") == staff_number
                for clef in attributes.findall(_q(ns, "clef"))
            ):
                return
        for note in measure.findall(_q(ns, "note")):
            if note.findtext(_q(ns, "staff"), "1").strip() != staff_number:
                continue
            pitch = note.find(_q(ns, "pitch"))
            if pitch is None:
                continue
            step = pitch.find(_q(ns, "step"))
            octave = pitch.find(_q(ns, "octave"))
            alter = pitch.find(_q(ns, "alter"))
            if step is None or octave is None or not step.text or not octave.text:
                continue
            new_step, new_alter, new_octave = transform_pitch(
                step.text.strip(),
                float(alter.text) if alter is not None and alter.text else 0.0,
                int(octave.text),
                old_sign,
                old_line,
                new_sign,
                new_line,
                old_octave_change,
                new_octave_change,
            )
            step.text = new_step
            octave.text = str(new_octave)
            if alter is not None:
                alter.text = str(new_alter)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
