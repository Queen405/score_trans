from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

from ..models.score import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock


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

_DURATION_PREFIXES = {
    "w": Fraction(4, 1),
    "h": Fraction(2, 1),
    "q": Fraction(1, 2),
    "s": Fraction(1, 4),
    "d": Fraction(1, 8),
}
_DURATION_TO_PREFIX = {value: key for key, value in _DURATION_PREFIXES.items()}
_DYNAMICS = {"p", "pp", "ppp", "mp", "mf", "f", "ff", "fff", "sfz", "fp"}


@dataclass(slots=True)
class JianpuOptions:
    key: str = "C"
    beats: int = 4
    beat_type: int = 4
    title: str = "简谱"
    tempo: int | None = None


@dataclass(slots=True)
class ParsedToken:
    kind: str
    value: str
    duration: Fraction = Fraction(1, 1)
    octave_shift: int = 0
    accidental: int = 0


@dataclass(slots=True)
class _Token:
    value: str
    line: int
    column: int


def musicxml_file_to_jianpu(path: Path) -> str:
    if path.suffix.lower() == ".mxl":
        return musicxml_to_jianpu(_read_mxl(path))
    return musicxml_to_jianpu(path.read_text(encoding="utf-8"))


def musicxml_to_jianpu(xml_text: str) -> str:
    from .musicxml import musicxml_to_score, score_to_jianpu_text

    return score_to_jianpu_text(musicxml_to_score(xml_text))


def jianpu_file_to_musicxml(path: Path, title: str = "Jianpu Import") -> str:
    return jianpu_to_musicxml(path.read_text(encoding="utf-8"), title=title)


def jianpu_to_musicxml(text: str, title: str = "Jianpu Import") -> str:
    score = parse_jianpu_score(text, title=title)
    return score_to_musicxml(score, title=title)


def parse_jianpu(text: str) -> tuple[JianpuOptions, list[ParsedToken]]:
    score = parse_jianpu_score(text)
    options = JianpuOptions(
        key=score.target_key,
        beats=score.beats,
        beat_type=score.beat_type,
        title=score.title,
    )
    tokens: list[ParsedToken] = []
    for measure in score.measures:
        for event in measure.events:
            if event.kind == "rest":
                tokens.append(ParsedToken("rest", "0", event.duration))
            else:
                pitch = event.pitches[0] if event.pitches else JianpuPitch(1)
                tokens.append(
                    ParsedToken("note", str(pitch.degree), event.duration, pitch.octave, pitch.accidental)
                )
        tokens.append(ParsedToken("bar", "|"))
    return options, tokens


def parse_jianpu_score(text: str, *, title: str | None = None) -> JianpuScore:
    normalized = migrate_legacy_jianpu(text)
    options, token_lines, lyrics = _read_new_syntax(normalized)
    if title and options.title == "简谱":
        options.title = title
    score = JianpuScore(title=options.title, target_key=options.key, source_key=options.key, beats=options.beats, beat_type=options.beat_type)

    current_events: list[Event] = []
    current_blocks: list[TextBlock] = []
    cursor = Fraction(0, 1)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    open_slur = False
    measure_number = 1

    def flush_measure() -> None:
        nonlocal current_events, current_blocks, cursor, measure_number
        if not current_events and not current_blocks and score.measures:
            return
        measure = Measure(
            source_number=str(measure_number),
            duration=score.measure_duration,
            events=current_events,
            text_blocks=current_blocks,
            beats_per_measure=score.beats,
            beat_type=score.beat_type,
            source_key=score.source_key,
            target_key=score.target_key,
        )
        _normalize_parsed_measure(measure, score)
        score.measures.append(measure)
        current_events = []
        current_blocks = []
        cursor = Fraction(0, 1)
        measure_number += 1

    for token in token_lines:
        raw = token.value
        if raw in {"|", "||", "|:", ":|"}:
            flush_measure()
            continue
        if raw.startswith("\\"):
            dynamic = raw[1:]
            if dynamic not in _DYNAMICS:
                raise _syntax_error(token, f"不支持的力度标记：{raw}，请使用 \\p、\\mp、\\f、\\ff 等")
            pending_dynamic = dynamic
            continue
        if raw.startswith("^"):
            pending_articulations.append(_articulation_name(raw[1:]))
            continue

        event = _parse_event_token(token)
        event.start = cursor
        if pending_dynamic:
            event.dynamic = pending_dynamic
            pending_dynamic = None
        if pending_articulations:
            event.articulations = pending_articulations
            event.articulation = pending_articulations[0]
            pending_articulations = []
        if raw.startswith("("):
            event.slur_start = True
            open_slur = True
        if raw.endswith(")") and open_slur:
            event.slur_stop = True
            open_slur = False
        current_events.append(event)
        cursor += event.duration

    if current_events or current_blocks or not score.measures:
        flush_measure()

    _apply_lyrics(score, lyrics)
    return score


def normalize_jianpu_text(text: str, *, title: str | None = None) -> str:
    from .musicxml import score_to_jianpu_text

    return score_to_jianpu_text(parse_jianpu_score(text, title=title))


def migrate_legacy_jianpu(text: str) -> str:
    if not _looks_legacy(text):
        return text

    out: list[str] = []
    body: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if body:
                body.append("")
            continue
        if line.startswith("@text"):
            continue
        lower = line.lower()
        if lower.startswith("key="):
            out.append(f"1={line.split('=', 1)[1].strip()}")
            continue
        if lower.startswith("time="):
            out.append(line.split("=", 1)[1].strip())
            continue
        migrated_parts: list[str] = []
        for part in re.findall(r"\|\||\|:|:\||\||[^\s|]+", line):
            if part == "-" and migrated_parts:
                migrated_parts[-1] += "-"
                continue
            migrated_parts.append(_migrate_legacy_token(part))
        body.append(" ".join(migrated_parts))
    return "\n".join(out + body)


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


def jianpu_to_html(jianpu_text: str) -> str:
    body = html.escape(jianpu_text).replace("\n", "<br>")
    return f"<html><body><pre style='font-size:20px;line-height:1.8'>{body}</pre></body></html>"


def _read_new_syntax(text: str) -> tuple[JianpuOptions, list[_Token], list[str]]:
    options = JianpuOptions()
    tokens: list[_Token] = []
    lyrics: list[str] = []
    saw_time = False
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("L:"):
            lyrics.extend(part for part in stripped[2:].strip().split() if part)
            continue
        if "=" in stripped and not stripped.startswith(("|", ":", "[", "\\", "^")):
            key, value = [part.strip() for part in stripped.split("=", 1)]
            if key == "1":
                options.key = value
                continue
            if key == "title":
                options.title = value or options.title
                continue
            if key == "tempo":
                options.tempo = int(value)
                continue
            if key.lower() in {"key", "time"}:
                raise ValueError(f"第 {line_no} 行：旧语法 `{key}=` 已废弃，请使用 `1=C` 和 `4/4`")
        if re.fullmatch(r"\d+/\d+", stripped) and not saw_time:
            beats, beat_type = stripped.split("/", 1)
            options.beats = int(beats)
            options.beat_type = int(beat_type)
            saw_time = True
            continue
        for match in re.finditer(r"\|\||\|:|:\||\||[^\s|]+", raw_line):
            tokens.append(_Token(match.group(0), line_no, match.start() + 1))
    return options, tokens, lyrics


def _parse_event_token(token: _Token) -> Event:
    raw = token.value
    work = raw.strip()
    slur_start = work.startswith("(")
    slur_stop = work.endswith(")")
    work = work.strip("()")
    tie_stop = work.startswith("~")
    if tie_stop:
        work = work[1:]
    tie_start = work.endswith("~")
    if tie_start:
        work = work[:-1]
    duration, work = _consume_duration_prefix(work)
    while work.endswith("-"):
        duration += Fraction(1, 1)
        work = work[:-1]
    dotted = work.endswith(".")
    if dotted:
        duration += duration / 2
        work = work[:-1]
    if "/" in work:
        raise _syntax_error(token, f"旧时值写法 `{token.value}` 已废弃，请使用 q/s/d 前缀，例如 q1 或 q[1+3]")
    if work.startswith("[") and work.endswith("]"):
        parts = [part.strip() for part in work[1:-1].split("+") if part.strip()]
        if not parts:
            raise _syntax_error(token, "和弦不能为空，请写成 [1+3+5]")
        event = Event(kind="note", duration=duration, pitches=[_parse_pitch(part, token) for part in parts])
        event.pitches.sort(key=lambda pitch: pitch.rank, reverse=True)
    elif work == "0":
        event = Event(kind="rest", duration=duration)
    else:
        event = Event(kind="note", duration=duration, pitches=[_parse_pitch(work, token)])
    event.dotted = 1 if dotted else 0
    event.tie_start = tie_start
    event.tie_stop = tie_stop
    event.slur_start = slur_start
    event.slur_stop = slur_stop
    return event


def _parse_pitch(raw: str, token: _Token) -> JianpuPitch:
    accidental = 0
    accidental_text: str | None = None
    value = raw
    if value.startswith("bb"):
        accidental = -2
        accidental_text = "bb"
        value = value[2:]
    elif value.startswith("x"):
        accidental = 2
        accidental_text = "x"
        value = value[1:]
    elif value.startswith(("n", "♮")):
        accidental = 0
        accidental_text = "♮"
        value = value[1:]
    elif value.startswith("#"):
        accidental = 1
        accidental_text = "#"
        value = value[1:]
    elif value.startswith("b"):
        accidental = -1
        accidental_text = "b"
        value = value[1:]
    if value.endswith("#"):
        accidental = 1
        accidental_text = "#"
        value = value[:-1]
    elif value.endswith("b"):
        accidental = -1
        accidental_text = "b"
        value = value[:-1]
    octave = value.count("'") - value.count(",")
    value = value.replace("'", "").replace(",", "")
    if value not in {"1", "2", "3", "4", "5", "6", "7"}:
        raise _syntax_error(token, f"不支持的简谱 token：{token.value}，请使用 1-7、0、#1、q1、[1+3+5] 等新语法")
    return JianpuPitch(int(value), octave=octave, accidental=accidental, accidental_text=accidental_text)


def _consume_duration_prefix(token: str) -> tuple[Fraction, str]:
    if token and token[0] in _DURATION_PREFIXES:
        return _DURATION_PREFIXES[token[0]], token[1:]
    return Fraction(1, 1), token


def _normalize_parsed_measure(measure: Measure, score: JianpuScore) -> None:
    target = score.measure_duration
    beat_duration = score.beat_duration
    measure.duration = target
    measure.beats = [Beat(index=i + 1, duration=beat_duration, start=i * beat_duration) for i in range(score.beats)]
    cursor = Fraction(0, 1)
    for event in measure.events:
        if event.start is None:
            event.start = cursor
        beat_index = min(score.beats - 1, max(0, int(event.start / beat_duration)))
        measure.beats[beat_index].events.append(event)
        cursor = event.start + event.duration
    if measure.span_duration > target:
        measure.validation_errors.append(f"小节超拍：实际 {measure.span_duration}，目标 {target}")


def _apply_lyrics(score: JianpuScore, lyrics: list[str]) -> None:
    if not lyrics:
        return
    lyric_index = 0
    for measure in score.measures:
        for event in measure.events:
            if lyric_index >= len(lyrics):
                return
            if event.kind != "note":
                continue
            event.lyric = lyrics[lyric_index]
            measure.text_blocks.append(
                TextBlock(text=lyrics[lyric_index], role="lyric", measure_number=measure.display_number, start=event.start)
            )
            lyric_index += 1


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


def _looks_legacy(text: str) -> bool:
    if re.search(r"(?im)^\s*(key|time)\s*=", text):
        return True
    body = "\n".join(line for line in text.splitlines() if not re.fullmatch(r"\s*\d+/\d+\s*", line))
    return bool(re.search(r"(^|\s)(?:[#[bnx♮]*[0-7]',*,*|0)/+\.?-*", body))


def _migrate_legacy_token(token: str) -> str:
    if token in {"|", "||", "|:", ":|"}:
        return token
    if token.startswith("[") and token.endswith("]"):
        parts = [_migrate_legacy_note(part) for part in token[1:-1].split("+") if part.strip()]
        durations = [prefix for prefix, _note in parts if prefix]
        notes = [note for _prefix, note in parts]
        prefix = durations[0] if durations and all(item == durations[0] for item in durations) else ""
        return f"{prefix}[{'+'.join(notes)}]"
    prefix, note = _migrate_legacy_note(token)
    return prefix + note


def _migrate_legacy_note(token: str) -> tuple[str, str]:
    work = token.strip()
    suffix = ""
    dotted = ""
    extension = ""
    while work.endswith("-"):
        extension += "-"
        work = work[:-1]
    if work.endswith("."):
        dotted = "."
        work = work[:-1]
    while work.endswith("/"):
        suffix += "/"
        work = work[:-1]
    prefix = {"/": "q", "//": "s", "///": "d"}.get(suffix, "")
    return prefix, work + dotted + extension


def _duration_prefix(duration: Fraction) -> str:
    if duration == Fraction(1, 1):
        return ""
    return _DURATION_TO_PREFIX.get(duration, "")


def _articulation_name(raw: str) -> str:
    return {
        ">": "accent",
        "-": "tenuto",
        ".": "staccato",
        "tr": "trill-mark",
    }.get(raw, raw)


def _syntax_error(token: _Token, message: str) -> ValueError:
    return ValueError(f"第 {token.line} 行第 {token.column} 列：{message}")


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag[1:].split("}", 1)[0]
    return ""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


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
