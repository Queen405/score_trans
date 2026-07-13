from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ...utils.safe_xml import safe_xml_fromstring
from .clef_transform import transform_pitch

_PROVENANCE_RE = re.compile(
    r"(?:^|__)(?P<role>[a-z]+)\d*-s(?P<sheet>\d+)-i(?P<inter>\d+)"
)


def apply_deletions(
    original_musicxml: str,
    deleted_source_ids: list[str],
    entity_index: dict[str, dict] | None = None,
) -> str:
    root = safe_xml_fromstring(
        original_musicxml.encode("utf-8"),
        allow_musicxml_doctype=True,
    )
    ns = _detect_namespace(root)

    for source_id in deleted_source_ids:
        entity_info = (entity_index or {}).get(source_id, {})
        tag = entity_info.get("tag", "")
        if tag in ("clef",):
            _delete_clef_with_pitch_transform(root, ns, source_id, entity_info)
        elif tag in ("time-whole", "time-custom"):
            _delete_attribute_element(root, ns, source_id, entity_info, "time")
        elif tag == "key":
            _delete_attribute_element(root, ns, source_id, entity_info, "key")
        elif tag in ("head", "rest"):
            _replace_note_with_rest(root, ns, source_id)
        elif tag == "alter":
            _remove_accidental(root, ns, source_id)
        else:
            _remove_note_by_provenance(root, ns, source_id)

    return _serialize(root)


def _detect_namespace(root: ET.Element) -> str:
    tag = root.tag
    if tag.startswith("{"):
        return tag.split("}")[0].lstrip("{")
    return ""


def _q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}" if ns else name


def _serialize(root: ET.Element) -> str:
    xml_str = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str


def _find_notes_by_provenance(root: ET.Element, ns: str, source_id: str) -> list[ET.Element]:
    parts = list(_PROVENANCE_RE.finditer(source_id))
    if not parts:
        return []
    sheet = parts[0].group("sheet")
    inter = parts[0].group("inter")
    contains = f"n-s{sheet}-i{inter}"
    result = []
    for note in root.iter(_q(ns, "note")):
        note_id = note.get("id", "")
        if contains in note_id:
            result.append(note)
    return result


def _replace_note_with_rest(root: ET.Element, ns: str, source_id: str) -> None:
    notes = _find_notes_by_provenance(root, ns, source_id)
    for note in notes:
        parent = _find_parent(root, note)
        if parent is None:
            continue
        if note.find(_q(ns, "chord")) is not None:
            parent.remove(note)
            continue
        pitch = note.find(_q(ns, "pitch"))
        if pitch is not None:
            note.remove(pitch)
        accidental = note.find(_q(ns, "accidental"))
        if accidental is not None:
            note.remove(accidental)
        for beam in note.findall(_q(ns, "beam")):
            note.remove(beam)
        notations = note.find(_q(ns, "notations"))
        if notations is not None:
            note.remove(notations)
        rest = ET.SubElement(note, _q(ns, "rest"))


def _remove_accidental(root: ET.Element, ns: str, source_id: str) -> None:
    parts = list(_PROVENANCE_RE.finditer(source_id))
    if not parts:
        return
    sheet = parts[0].group("sheet")
    inter = parts[0].group("inter")
    contains = f"a-s{sheet}-i{inter}"
    for note in root.iter(_q(ns, "note")):
        note_id = note.get("id", "")
        if contains in note_id:
            accidental = note.find(_q(ns, "accidental"))
            if accidental is not None:
                note.remove(accidental)
            pitch = note.find(_q(ns, "pitch"))
            if pitch is not None:
                alter = pitch.find(_q(ns, "alter"))
                if alter is not None:
                    pitch.remove(alter)


def _remove_note_by_provenance(root: ET.Element, ns: str, source_id: str) -> None:
    notes = _find_notes_by_provenance(root, ns, source_id)
    for note in notes:
        parent = _find_parent(root, note)
        if parent is None:
            continue
        parent.remove(note)


def _delete_clef_with_pitch_transform(
    root: ET.Element,
    ns: str,
    source_id: str,
    entity_info: dict,
) -> None:
    clef_sign = None
    clef_line = None
    target_clef_elem = None
    target_attrs = None

    for part in root.iter(_q(ns, "part")):
        for measure in part.findall(_q(ns, "measure")):
            attrs = measure.find(_q(ns, "attributes"))
            if attrs is None:
                continue
            for clef in attrs.findall(_q(ns, "clef")):
                sign_elem = clef.find(_q(ns, "sign"))
                line_elem = clef.find(_q(ns, "line"))
                if sign_elem is not None and sign_elem.text:
                    clef_sign = sign_elem.text.strip()
                    clef_line = int(line_elem.text) if line_elem is not None and line_elem.text else 2
                    target_clef_elem = clef
                    target_attrs = attrs
                    break
            if target_clef_elem is not None:
                break
        if target_clef_elem is not None:
            break

    if target_clef_elem is None or target_attrs is None or clef_sign is None:
        return

    target_attrs.remove(target_clef_elem)

    _transform_notes_after_clef(root, ns, clef_sign, clef_line or 2)


def _transform_notes_after_clef(
    root: ET.Element,
    ns: str,
    old_sign: str,
    old_line: int,
) -> None:
    found_clef = False
    for part in root.iter(_q(ns, "part")):
        for measure in part.findall(_q(ns, "measure")):
            attrs = measure.find(_q(ns, "attributes"))
            if attrs is not None and not found_clef:
                for clef in attrs.findall(_q(ns, "clef")):
                    found_clef = True
                    break
            if not found_clef:
                continue
            if attrs is not None:
                for clef in attrs.findall(_q(ns, "clef")):
                    return
            for note in measure.findall(_q(ns, "note")):
                pitch = note.find(_q(ns, "pitch"))
                if pitch is None:
                    continue
                step_elem = pitch.find(_q(ns, "step"))
                octave_elem = pitch.find(_q(ns, "octave"))
                alter_elem = pitch.find(_q(ns, "alter"))
                if step_elem is None or octave_elem is None or not step_elem.text or not octave_elem.text:
                    continue
                step = step_elem.text.strip()
                octave = int(octave_elem.text.strip())
                alter = float(alter_elem.text) if alter_elem is not None and alter_elem.text else 0.0
                new_step, new_alter, new_octave = transform_pitch(
                    step, alter, octave, old_sign, old_line
                )
                step_elem.text = new_step
                octave_elem.text = str(new_octave)
                if alter_elem is not None:
                    alter_elem.text = str(new_alter)


def _delete_attribute_element(
    root: ET.Element,
    ns: str,
    source_id: str,
    entity_info: dict,
    elem_name: str,
) -> None:
    for part in root.iter(_q(ns, "part")):
        for measure in part.findall(_q(ns, "measure")):
            attrs = measure.find(_q(ns, "attributes"))
            if attrs is None:
                continue
            target = attrs.find(_q(ns, elem_name))
            if target is not None:
                attrs.remove(target)
                return


def _find_parent(root: ET.Element, child: ET.Element) -> ET.Element | None:
    for parent in root.iter():
        if child in list(parent):
            return parent
    return None
