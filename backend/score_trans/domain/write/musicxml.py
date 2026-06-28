from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from math import lcm

from ..constants import (
    KEY_TO_FIFTHS,
    KEY_TO_TONIC,
    DEGREE_TO_MAJOR_OFFSET,
    SEMITONE_TO_STEP,
)
from ..performance_marks import event_mark_ids, get_performance_mark
from ..xml_utils import _indent
from ...models.score import Event, JianpuPitch, JianpuScore


def score_to_musicxml(score: JianpuScore, title: str = "Jianpu Import") -> str:
    divisions = _score_divisions(score)
    root = ET.Element("score-partwise", {"version": "4.0"})
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = title or score.title
    identification = ET.SubElement(root, "identification")
    miscellaneous = ET.SubElement(identification, "miscellaneous")
    profile_field = ET.SubElement(
        miscellaneous,
        "miscellaneous-field",
        {"name": "score-trans-instrument-profile"},
    )
    profile_field.text = score.instrument_profile
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
    ET.SubElement(score_part, "part-name").text = {
        "erhu": "Erhu",
        "zhongruan": "Zhongruan",
    }.get(score.instrument_profile, "Music")
    part = ET.SubElement(root, "part", {"id": "P1"})

    previous_key: str | None = None
    previous_time: tuple[int, int] | None = None
    for index, source_measure in enumerate(score.measures, start=1):
        measure = ET.SubElement(part, "measure", {"number": str(index)})
        measure_key = getattr(source_measure, "target_key", score.target_key)
        measure_beats = getattr(source_measure, "beats_per_measure", score.beats)
        measure_beat_type = getattr(source_measure, "beat_type", score.beat_type)
        measure_time = (measure_beats, measure_beat_type)
        if index == 1 or measure_key != previous_key or measure_time != previous_time:
            attrs = ET.SubElement(measure, "attributes")
            if index == 1:
                ET.SubElement(attrs, "divisions").text = str(divisions)
            if index == 1 or measure_key != previous_key:
                key = ET.SubElement(attrs, "key")
                ET.SubElement(key, "fifths").text = str(
                    KEY_TO_FIFTHS.get(measure_key, 0)
                )
            if index == 1 or measure_time != previous_time:
                time = ET.SubElement(attrs, "time")
                ET.SubElement(time, "beats").text = str(measure_beats)
                ET.SubElement(time, "beat-type").text = str(measure_beat_type)
            if index == 1:
                clef = ET.SubElement(attrs, "clef")
                ET.SubElement(clef, "sign").text = "G"
                ET.SubElement(clef, "line").text = "2"
            previous_key = measure_key
            previous_time = measure_time
        for event in source_measure.events:
            _append_event_xml(measure, event, measure_key, divisions)

    _indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode"
    )


def _score_divisions(score: JianpuScore) -> int:
    divisions = 8
    for measure in score.measures:
        for event in measure.events:
            divisions = lcm(divisions, event.duration.denominator)
    return max(1, divisions)


def _append_event_xml(
    parent: ET.Element, event: Event, measure_key: str, divisions: int
) -> None:
    pitches = event.pitches or [None]
    for index, pitch in enumerate(pitches):
        note = ET.SubElement(parent, "note")
        if index > 0:
            ET.SubElement(note, "chord")
        if event.kind == "rest" or pitch is None:
            ET.SubElement(note, "rest")
        else:
            _append_pitch_xml(note, pitch, measure_key)
        duration_units = max(1, int(event.duration * divisions))
        ET.SubElement(note, "duration").text = str(duration_units)
        note_type, dotted = _fraction_to_type(_notated_duration(event))
        ET.SubElement(note, "type").text = note_type
        if dotted:
            ET.SubElement(note, "dot")
        if event.tuplet_count:
            normal_notes = _tuplet_normal_notes(event.tuplet_count)
            if normal_notes != event.tuplet_count:
                time_mod = ET.SubElement(note, "time-modification")
                ET.SubElement(time_mod, "actual-notes").text = str(event.tuplet_count)
                ET.SubElement(time_mod, "normal-notes").text = str(normal_notes)
        if event.tie_start:
            ET.SubElement(note, "tie", {"type": "start"})
        if event.tie_stop:
            ET.SubElement(note, "tie", {"type": "stop"})
        if index == 0:
            _append_notations(note, event)
        if event.lyric and index == 0:
            lyric = ET.SubElement(note, "lyric")
            ET.SubElement(lyric, "text").text = event.lyric


def _append_notations(note: ET.Element, event: Event) -> None:
    articulations = list(
        event.articulations
        or ([event.articulation] if event.articulation else [])
    )
    marks = event_mark_ids(
        articulations,
        list(event.ornaments),
        list(event.technical),
    )
    if not any(
        (
            marks,
            event.slur_start,
            event.slur_stop,
            event.slide_start,
            event.slide_stop,
            event.tuplet_start,
            event.tuplet_stop,
            event.dynamic,
        )
    ):
        return

    notations = ET.SubElement(note, "notations")
    if event.slur_stop:
        ET.SubElement(notations, "slur", {"type": "stop"})
    if event.slur_start:
        ET.SubElement(notations, "slur", {"type": "start"})
    if event.slide_stop:
        ET.SubElement(notations, "slide", {"type": "stop"})
    if event.slide_start:
        ET.SubElement(notations, "slide", {"type": "start"})
    if event.tuplet_start:
        ET.SubElement(notations, "tuplet", {"type": "start"})
    if event.tuplet_stop:
        ET.SubElement(notations, "tuplet", {"type": "stop"})

    groups: dict[str, ET.Element] = {}
    for mark_id in marks:
        mark = get_performance_mark(mark_id)
        if mark is None or mark.musicxml_section is None:
            continue
        if mark.musicxml_section == "notations":
            ET.SubElement(notations, mark.musicxml_name or mark.id)
            continue
        group = groups.get(mark.musicxml_section)
        if group is None:
            group = ET.SubElement(notations, mark.musicxml_section)
            groups[mark.musicxml_section] = group
        _append_mark_xml(group, mark_id)

    if event.dynamic:
        dynamics = ET.SubElement(notations, "dynamics")
        ET.SubElement(dynamics, event.dynamic)


def _append_mark_xml(parent: ET.Element, mark_id: str) -> None:
    mark = get_performance_mark(mark_id)
    if mark is None:
        return
    if mark.custom_musicxml:
        element_name = {
            "articulations": "other-articulation",
            "ornaments": "other-ornament",
        }.get(mark.musicxml_section or "", "other-technical")
        ET.SubElement(parent, element_name).text = mark.custom_musicxml
        return
    name = mark.musicxml_name or mark.id
    if mark_id == "tremolo":
        ET.SubElement(parent, "tremolo", {"type": "single"}).text = "3"
        return
    if mark_id in {"natural-harmonic", "artificial-harmonic"}:
        harmonic = ET.SubElement(parent, "harmonic")
        ET.SubElement(
            harmonic,
            "natural" if mark_id == "natural-harmonic" else "artificial",
        )
        return
    if mark_id.startswith("fingering-"):
        ET.SubElement(parent, "fingering").text = mark_id.rsplit("-", 1)[-1]
        return
    ET.SubElement(parent, name)


def _append_pitch_xml(
    note: ET.Element, pitch_value: JianpuPitch, measure_key: str
) -> None:
    tonic = KEY_TO_TONIC.get(measure_key, 0)
    semitone = (
        tonic + DEGREE_TO_MAJOR_OFFSET[pitch_value.degree] + pitch_value.accidental
    ) % 12
    step, alter = SEMITONE_TO_STEP[semitone]
    pitch = ET.SubElement(note, "pitch")
    ET.SubElement(pitch, "step").text = step
    if alter:
        ET.SubElement(pitch, "alter").text = str(alter)
    ET.SubElement(pitch, "octave").text = str(4 + pitch_value.octave)


def _fraction_to_type(duration: Fraction) -> tuple[str, bool]:
    base = {
        Fraction(4, 1): "whole",
        Fraction(2, 1): "half",
        Fraction(1, 1): "quarter",
        Fraction(1, 2): "eighth",
        Fraction(1, 4): "16th",
        Fraction(1, 8): "32nd",
    }
    if duration in base:
        return base[duration], False
    for value, name in base.items():
        if duration == value + value / 2:
            return name, True
    return "quarter", False


def _notated_duration(event: Event) -> Fraction:
    if not event.tuplet_count:
        return event.duration
    return Fraction(1, _tuplet_normal_notes(event.tuplet_count))


def _tuplet_normal_notes(actual_notes: int) -> int:
    normal_notes = 1
    while normal_notes * 2 <= actual_notes:
        normal_notes *= 2
    return max(1, normal_notes)



