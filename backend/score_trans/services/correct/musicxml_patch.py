from __future__ import annotations

from collections.abc import Mapping
import xml.etree.ElementTree as ET

from ...utils.safe_xml import safe_xml_fromstring
from .clef_transform import transform_pitch
from .entity_service import CorrectableEntity


def apply_deletions(
    original_musicxml: str,
    deleted_source_ids: list[str],
    entities: Mapping[str, CorrectableEntity],
) -> str:
    root = safe_xml_fromstring(
        original_musicxml.encode("utf-8"),
        allow_musicxml_doctype=True,
    )
    ns = _detect_namespace(root)

    unknown = [
        source_id for source_id in deleted_source_ids if source_id not in entities
    ]
    if unknown:
        raise ValueError(f"无法定位待删除标记：{', '.join(unknown)}")

    for source_id in dict.fromkeys(deleted_source_ids):
        entity = entities[source_id]
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
        else:  # Defensive: entity_service must never expose unsupported tags.
            raise ValueError(f"不支持删除的标记类型：{entity.tag}")

    return _serialize(root, ns)


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


def _matching_elements(root: ET.Element, entity: CorrectableEntity) -> list[ET.Element]:
    return [
        element
        for element in root.iter()
        if entity.musicxml_locator in element.get(entity.musicxml_attribute, "")
    ]


def _single_matching_element(root: ET.Element, entity: CorrectableEntity) -> ET.Element:
    matches = _matching_elements(root, entity)
    if len(matches) != 1:
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


def _target_note(root: ET.Element, ns: str, entity: CorrectableEntity) -> ET.Element:
    matched = _single_matching_element(root, entity)
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
    parent = _parent(root, note)
    if parent is None:
        raise ValueError(f"音符 {entity.source_id} 缺少小节容器")
    parent.remove(note)


def _remove_accidental(root: ET.Element, ns: str, entity: CorrectableEntity) -> None:
    note = _target_note(root, ns, entity)
    accidental = note.find(_q(ns, "accidental"))
    if accidental is not None:
        note.remove(accidental)
    pitch = note.find(_q(ns, "pitch"))
    alter = pitch.find(_q(ns, "alter")) if pitch is not None else None
    if pitch is not None and alter is not None:
        pitch.remove(alter)


def _delete_attribute_element(
    root: ET.Element,
    entity: CorrectableEntity,
    expected_local_name: str,
) -> None:
    target = _single_matching_element(root, entity)
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
