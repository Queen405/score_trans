from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction

from ..constants import KEY_TO_FIFTHS, KEY_TO_TONIC, DEGREE_TO_MAJOR_OFFSET, SEMITONE_TO_STEP, DURATION_TO_PREFIX
from ..xml_utils import _indent
from ...models.score import Event, JianpuPitch, JianpuScore


def score_to_musicxml(score: JianpuScore, title: str = "Jianpu Import") -> str:
    divisions = 8
    root = ET.Element("score-partwise", {"version": "3.1"})
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = title or score.title
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
    ET.SubElement(score_part, "part-name").text = "Music"
    part = ET.SubElement(root, "part", {"id": "P1"})

    for index, source_measure in enumerate(score.measures, start=1):
        measure = ET.SubElement(part, "measure", {"number": str(index)})
        if index == 1:
            attrs = ET.SubElement(measure, "attributes")
            ET.SubElement(attrs, "divisions").text = str(divisions)
            key = ET.SubElement(attrs, "key")
            ET.SubElement(key, "fifths").text = str(KEY_TO_FIFTHS.get(score.target_key, 0))
            time = ET.SubElement(attrs, "time")
            ET.SubElement(time, "beats").text = str(score.beats)
            ET.SubElement(time, "beat-type").text = str(score.beat_type)
            clef = ET.SubElement(attrs, "clef")
            ET.SubElement(clef, "sign").text = "G"
            ET.SubElement(clef, "line").text = "2"
        for event in source_measure.events:
            _append_event_xml(measure, event, score, divisions)

    _indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _append_event_xml(parent: ET.Element, event: Event, score: JianpuScore, divisions: int) -> None:
    pitches = event.pitches or [None]
    for index, pitch in enumerate(pitches):
        note = ET.SubElement(parent, "note")
        if index > 0:
            ET.SubElement(note, "chord")
        if event.kind == "rest" or pitch is None:
            ET.SubElement(note, "rest")
        else:
            _append_pitch_xml(note, pitch, score)
        duration_units = max(1, int(event.duration * divisions))
        ET.SubElement(note, "duration").text = str(duration_units)
        note_type, dotted = _fraction_to_type(event.duration)
        ET.SubElement(note, "type").text = note_type
        if dotted:
            ET.SubElement(note, "dot")
        if event.tie_start:
            ET.SubElement(note, "tie", {"type": "start"})
        if event.tie_stop:
            ET.SubElement(note, "tie", {"type": "stop"})
        if event.lyric and index == 0:
            lyric = ET.SubElement(note, "lyric")
            ET.SubElement(lyric, "text").text = event.lyric


def _append_pitch_xml(note: ET.Element, pitch_value: JianpuPitch, score: JianpuScore) -> None:
    tonic = KEY_TO_TONIC.get(score.target_key, 0)
    semitone = (tonic + DEGREE_TO_MAJOR_OFFSET[pitch_value.degree] + pitch_value.accidental) % 12
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


def _duration_prefix(duration: Fraction) -> str:
    if duration == Fraction(1, 1):
        return ""
    return DURATION_TO_PREFIX.get(duration, "")
