from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile


STEP_TO_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SEMITONE_TO_STEP = {
    0: ("C", 0),
    1: ("C", 1),
    2: ("D", 0),
    3: ("D", 1),
    4: ("E", 0),
    5: ("F", 0),
    6: ("F", 1),
    7: ("G", 0),
    8: ("G", 1),
    9: ("A", 0),
    10: ("A", 1),
    11: ("B", 0),
}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
FIFTHS_TO_KEY = {
    -7: "Cb",
    -6: "Gb",
    -5: "Db",
    -4: "Ab",
    -3: "Eb",
    -2: "Bb",
    -1: "F",
    0: "C",
    1: "G",
    2: "D",
    3: "A",
    4: "E",
    5: "B",
    6: "F#",
    7: "C#",
}
KEY_TO_FIFTHS = {value: key for key, value in FIFTHS_TO_KEY.items()}
KEY_TO_TONIC = {
    "C": 0,
    "G": 7,
    "D": 2,
    "A": 9,
    "E": 4,
    "B": 11,
    "F#": 6,
    "C#": 1,
    "F": 5,
    "Bb": 10,
    "Eb": 3,
    "Ab": 8,
    "Db": 1,
    "Gb": 6,
    "Cb": 11,
}
DEGREE_TO_MAJOR_OFFSET = {index + 1: offset for index, offset in enumerate(MAJOR_SCALE)}


@dataclass(slots=True)
class JianpuOptions:
    key: str = "C"
    beats: int = 4
    beat_type: int = 4


@dataclass(slots=True)
class ParsedToken:
    kind: str
    value: str
    duration: Fraction = Fraction(1, 1)
    octave_shift: int = 0
    accidental: int = 0


def musicxml_file_to_jianpu(path: Path) -> str:
    if path.suffix.lower() == ".mxl":
        return musicxml_to_jianpu(_read_mxl(path))
    return musicxml_to_jianpu(path.read_text(encoding="utf-8"))


def musicxml_to_jianpu(xml_text: str) -> str:
    root = ET.fromstring(xml_text)
    ns = _namespace(root.tag)
    part = root.find(_q(ns, "part"))
    if part is None:
        return ""

    key = "C"
    beats = "4"
    beat_type = "4"
    lines: list[str] = []

    for measure in part.findall(_q(ns, "measure")):
        attrs = measure.find(_q(ns, "attributes"))
        if attrs is not None:
            fifths = _text(attrs.find(f"{_q(ns, 'key')}/{_q(ns, 'fifths')}"))
            if fifths is not None:
                key = FIFTHS_TO_KEY.get(int(fifths), "C")
            beats_text = _text(attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beats')}"))
            beat_type_text = _text(attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beat-type')}"))
            if beats_text and beat_type_text:
                beats, beat_type = beats_text, beat_type_text

        tokens: list[str] = []
        for note in measure.findall(_q(ns, "note")):
            if note.find(_q(ns, "chord")) is not None:
                tokens[-1] = f"[{tokens[-1]}+{_note_to_token(note, ns, key)}]"
                continue
            tokens.append(_note_to_token(note, ns, key))
        if tokens:
            lines.append(" ".join(tokens))

    header = [f"key={key}", f"time={beats}/{beat_type}"]
    return "\n".join(header + [" | ".join(lines) + (" |" if lines else "")])


def jianpu_file_to_musicxml(path: Path, title: str = "Jianpu Import") -> str:
    return jianpu_to_musicxml(path.read_text(encoding="utf-8"), title=title)


def jianpu_to_musicxml(text: str, title: str = "Jianpu Import") -> str:
    options, tokens = parse_jianpu(text)
    divisions = 4
    measure_number = 1
    current_measure: list[ParsedToken] = []
    measures: list[list[ParsedToken]] = []

    for token in tokens:
        if token.kind == "bar":
            measures.append(current_measure)
            current_measure = []
        else:
            current_measure.append(token)
    if current_measure or not measures:
        measures.append(current_measure)

    score = ET.Element("score-partwise", {"version": "3.1"})
    work = ET.SubElement(score, "work")
    ET.SubElement(work, "work-title").text = title
    part_list = ET.SubElement(score, "part-list")
    score_part = ET.SubElement(part_list, "score-part", {"id": "P1"})
    ET.SubElement(score_part, "part-name").text = "Music"
    part = ET.SubElement(score, "part", {"id": "P1"})

    for measure_tokens in measures:
        measure = ET.SubElement(part, "measure", {"number": str(measure_number)})
        if measure_number == 1:
            attrs = ET.SubElement(measure, "attributes")
            ET.SubElement(attrs, "divisions").text = str(divisions)
            key = ET.SubElement(attrs, "key")
            ET.SubElement(key, "fifths").text = str(KEY_TO_FIFTHS.get(options.key, 0))
            time = ET.SubElement(attrs, "time")
            ET.SubElement(time, "beats").text = str(options.beats)
            ET.SubElement(time, "beat-type").text = str(options.beat_type)
            clef = ET.SubElement(attrs, "clef")
            ET.SubElement(clef, "sign").text = "G"
            ET.SubElement(clef, "line").text = "2"

        for token in measure_tokens:
            _append_note(measure, token, options, divisions)
        measure_number += 1

    _indent(score)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(score, encoding="unicode")


def parse_jianpu(text: str) -> tuple[JianpuOptions, list[ParsedToken]]:
    options = JianpuOptions()
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("# "):
            continue
        if "=" in line:
            key, value = [part.strip() for part in line.split("=", 1)]
            if key.lower() == "key":
                options.key = value
                continue
            if key.lower() == "time":
                beats, beat_type = value.split("/", 1)
                options.beats = int(beats)
                options.beat_type = int(beat_type)
                continue
        cleaned_lines.append(line)

    tokens: list[ParsedToken] = []
    last_note: ParsedToken | None = None
    for raw in re.findall(r"\||[^\s|]+", " ".join(cleaned_lines)):
        if raw == "|":
            tokens.append(ParsedToken("bar", raw))
            continue
        if raw == "-":
            if last_note is not None:
                last_note.duration += Fraction(1, 1)
            continue
        parsed = _parse_note_token(raw)
        tokens.append(parsed)
        if parsed.kind in {"note", "rest"}:
            last_note = parsed
    return options, tokens


def _parse_note_token(raw: str) -> ParsedToken:
    duration = Fraction(1, 1)
    accidental = 0
    extension = 0
    while raw.endswith("-"):
        extension += 1
        raw = raw[:-1]
    while raw.endswith("/"):
        duration /= 2
        raw = raw[:-1]
    if raw.endswith("."):
        duration += duration / 2
        raw = raw[:-1]
    duration += extension
    if raw.startswith("bb"):
        accidental = -2
        raw = raw[2:]
    elif raw.startswith("x"):
        accidental = 2
        raw = raw[1:]
    elif raw.startswith(("n", "♮")):
        accidental = 0
        raw = raw[1:]
    elif raw.startswith("#"):
        accidental = 1
        raw = raw[1:]
    elif raw.startswith("b"):
        accidental = -1
        raw = raw[1:]

    octave_shift = raw.count("'") - raw.count(",")
    raw = raw.replace("'", "").replace(",", "")
    if raw == "0":
        return ParsedToken("rest", raw, duration)
    if raw not in {"1", "2", "3", "4", "5", "6", "7"}:
        raise ValueError(f"不支持的简谱 token：{raw}")
    return ParsedToken("note", raw, duration, octave_shift, accidental)


def _note_to_token(note: ET.Element, ns: str, key: str) -> str:
    rest = note.find(_q(ns, "rest"))
    duration_suffix = _duration_suffix(note, ns)
    if rest is not None:
        return "0" + duration_suffix

    pitch = note.find(_q(ns, "pitch"))
    if pitch is None:
        return "?"
    step = _text(pitch.find(_q(ns, "step"))) or "C"
    alter = int(float(_text(pitch.find(_q(ns, "alter"))) or "0"))
    octave = int(_text(pitch.find(_q(ns, "octave"))) or "4")
    semitone = (STEP_TO_SEMITONE[step] + alter) % 12
    tonic = KEY_TO_TONIC.get(key, 0)
    relative = (semitone - tonic) % 12

    if relative in MAJOR_SCALE:
        accidental = ""
        degree = MAJOR_SCALE.index(relative) + 1
    elif (relative - 1) % 12 in MAJOR_SCALE:
        accidental = "#"
        degree = MAJOR_SCALE.index((relative - 1) % 12) + 1
    else:
        accidental = "b"
        degree = MAJOR_SCALE.index((relative + 1) % 12) + 1

    octave_marks = "'" * max(0, octave - 4) + "," * max(0, 4 - octave)
    return f"{accidental}{degree}{octave_marks}{duration_suffix}"


def _duration_suffix(note: ET.Element, ns: str) -> str:
    type_text = _text(note.find(_q(ns, "type"))) or "quarter"
    suffix = {
        "whole": "---",
        "half": "-",
        "quarter": "",
        "eighth": "/",
        "16th": "//",
        "32nd": "///",
    }.get(type_text, "")
    if note.find(_q(ns, "dot")) is not None:
        suffix += "."
    return suffix


def _append_note(parent: ET.Element, token: ParsedToken, options: JianpuOptions, divisions: int) -> None:
    note = ET.SubElement(parent, "note")
    if token.kind == "rest":
        ET.SubElement(note, "rest")
    else:
        tonic = KEY_TO_TONIC.get(options.key, 0)
        degree = int(token.value)
        semitone = (tonic + DEGREE_TO_MAJOR_OFFSET[degree] + token.accidental) % 12
        step, alter = SEMITONE_TO_STEP[semitone]
        pitch = ET.SubElement(note, "pitch")
        ET.SubElement(pitch, "step").text = step
        if alter:
            ET.SubElement(pitch, "alter").text = str(alter)
        ET.SubElement(pitch, "octave").text = str(4 + token.octave_shift)

    duration_units = max(1, int(token.duration * divisions))
    ET.SubElement(note, "duration").text = str(duration_units)
    note_type, dotted = _fraction_to_type(token.duration)
    ET.SubElement(note, "type").text = note_type
    if dotted:
        ET.SubElement(note, "dot")


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


def jianpu_to_html(jianpu_text: str) -> str:
    body = html.escape(jianpu_text).replace("\n", "<br>")
    return f"<html><body><pre style='font-size:20px;line-height:1.8'>{body}</pre></body></html>"


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    return element.text.strip()


def _indent(element: ET.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = i + "  "
        for child in element:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not element.tail or not element.tail.strip()):
        element.tail = i


def _read_mxl(path: Path) -> str:
    with ZipFile(path) as archive:
        names = archive.namelist()
        musicxml_names = [
            name
            for name in names
            if name.lower().endswith((".xml", ".musicxml")) and not name.startswith("META-INF/")
        ]
        if not musicxml_names:
            raise ValueError(f"MXL 文件中没有找到 MusicXML：{path}")
        with archive.open(musicxml_names[0]) as handle:
            return handle.read().decode("utf-8")
