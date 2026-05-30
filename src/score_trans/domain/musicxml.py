from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

from .jianpu import FIFTHS_TO_KEY, KEY_TO_TONIC, MAJOR_SCALE, STEP_TO_SEMITONE
from .models import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock


def musicxml_path_to_score(
    path: Path,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
) -> JianpuScore:
    return musicxml_to_score(_read_musicxml(path), target_key, start_measure_number, title)


def read_musicxml_text(path: Path) -> str:
    return _read_musicxml(path)


def musicxml_to_score(
    xml_text: str,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
) -> JianpuScore:
    root = ET.fromstring(xml_text)
    ns = _namespace(root.tag)
    part = root.find(_q(ns, "part"))
    if part is None:
        return JianpuScore(title=title or "简谱", target_key=target_key)

    extracted_title = title or _extract_title(root, ns)
    score = JianpuScore(title=extracted_title, target_key=target_key)
    if extracted_title:
        score.text_blocks.append(TextBlock(text=extracted_title, role="title"))
    score.text_blocks.extend(_extract_part_names(root, ns))
    current_key = "C"
    current_beats = 4
    current_beat_type = 4
    divisions = 1

    for index, xml_measure in enumerate(part.findall(_q(ns, "measure")), start=1):
        attrs = xml_measure.find(_q(ns, "attributes"))
        if attrs is not None:
            divisions = int(_text(attrs.find(_q(ns, "divisions"))) or divisions)
            fifths = _text(attrs.find(f"{_q(ns, 'key')}/{_q(ns, 'fifths')}"))
            if fifths is not None:
                current_key = FIFTHS_TO_KEY.get(int(fifths), "C")
            beats_text = _text(attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beats')}"))
            beat_type_text = _text(attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beat-type')}"))
            if beats_text and beat_type_text:
                current_beats = int(beats_text)
                current_beat_type = int(beat_type_text)
                score.beats = current_beats
                score.beat_type = current_beat_type
            score.source_key = current_key

        display_number = (
            start_measure_number + index - 1
            if start_measure_number is not None
            else _display_measure_number(xml_measure, index)
        )
        measure = Measure(
            source_number=xml_measure.get("number", str(index)),
            display_measure_number=display_number,
            duration=Fraction(current_beats * 4, current_beat_type),
            beats_per_measure=current_beats,
            beat_type=current_beat_type,
            source_key=current_key,
            target_key=target_key,
        )
        measure.text_blocks.append(TextBlock(text=str(display_number), role="measure_number", measure_number=display_number))
        _read_measure_events(xml_measure, ns, divisions, target_key, measure)
        _normalize_measure(measure, current_beats, current_beat_type)
        score.measures.append(measure)

    return score


def score_to_jianpu_text(score: JianpuScore) -> str:
    lines = [f"key={score.target_key}", f"time={score.beats}/{score.beat_type}"]
    measures = []
    for measure in score.measures:
        events = measure.events
        tokens = [_event_to_token(event) for event in events]
        measures.append(" ".join(tokens))
    lines.append(" | ".join(measures) + (" |" if measures else ""))
    return "\n".join(lines)


def _read_measure_events(xml_measure: ET.Element, ns: str, divisions: int, target_key: str, measure: Measure) -> None:
    last_event: Event | None = None
    cursor = Fraction(0, 1)
    for child in list(xml_measure):
        tag = _local_name(child.tag)
        if tag == "backup":
            duration = _duration_from_child(child, ns, divisions)
            cursor = max(Fraction(0, 1), cursor - duration)
            last_event = None
            continue
        if tag == "forward":
            cursor += _duration_from_child(child, ns, divisions)
            last_event = None
            continue
        if tag == "direction":
            measure.text_blocks.extend(_direction_text_blocks(child, ns, measure.display_measure_number))
            continue
        if tag != "note":
            continue

        note = child
        duration = Fraction(int(_text(note.find(_q(ns, "duration"))) or 0), divisions)
        if duration <= 0:
            duration = Fraction(1, 1)

        if note.find(_q(ns, "chord")) is not None and last_event is not None and last_event.kind == "note":
            pitch = _note_pitch(note, ns, target_key)
            if pitch:
                last_event.pitches.append(pitch)
                last_event.pitches.sort(key=lambda value: value.rank, reverse=True)
            continue

        if note.find(_q(ns, "rest")) is not None:
            event = Event(kind="rest", duration=duration)
        else:
            pitch = _note_pitch(note, ns, target_key)
            event = Event(kind="note", duration=duration, pitches=[pitch] if pitch else [])
        event.dotted = len(note.findall(_q(ns, "dot")))
        event.tie_start = any(tie.get("type") == "start" for tie in note.findall(_q(ns, "tie")))
        event.tie_stop = any(tie.get("type") == "stop" for tie in note.findall(_q(ns, "tie")))
        event.voice = _text(note.find(_q(ns, "voice")))
        event.staff = _text(note.find(_q(ns, "staff")))
        event.start = cursor
        notations = note.find(_q(ns, "notations"))
        if notations is not None:
            event.slur_start = any(slur.get("type") == "start" for slur in notations.findall(_q(ns, "slur")))
            event.slur_stop = any(slur.get("type") == "stop" for slur in notations.findall(_q(ns, "slur")))
            if notations.find(_q(ns, "fermata")) is not None:
                event.articulation = "fermata"
            else:
                event.articulation = _first_child_name(notations.find(_q(ns, "articulations")), ns)
            event.dynamic = _first_child_name(notations.find(_q(ns, "dynamics")), ns)
        lyric = note.find(_q(ns, "lyric"))
        if lyric is not None:
            event.lyric = _text(lyric.find(_q(ns, "text")))
            if event.lyric:
                measure.text_blocks.append(TextBlock(text=event.lyric, role="lyric", measure_number=measure.display_measure_number))
        measure.events.append(event)
        last_event = event
        cursor += duration


def _normalize_measure(measure: Measure, beats: int, beat_type: int) -> None:
    target = Fraction(beats * 4, beat_type)
    actual = measure.span_duration
    if actual < target:
        measure.events.append(Event(kind="rest", duration=target - actual, start=actual, generated=True))
    elif actual > target:
        measure.validation_errors.append(f"小节超拍：实际 {actual}，目标 {target}")

    beat_duration = Fraction(4, beat_type)
    measure.duration = target
    measure.beats_per_measure = beats
    measure.beat_type = beat_type
    measure.beats = [Beat(index=index + 1, duration=beat_duration, start=index * beat_duration) for index in range(beats)]
    cursor = Fraction(0, 1)
    for event in measure.events:
        if event.start is None:
            event.start = cursor
        beat_index = min(beats - 1, max(0, int(event.start / beat_duration)))
        measure.beats[beat_index].events.append(event)
        cursor = event.start + event.duration


def _note_pitch(note: ET.Element, ns: str, target_key: str) -> JianpuPitch | None:
    pitch = note.find(_q(ns, "pitch"))
    if pitch is None:
        return None
    step = _text(pitch.find(_q(ns, "step"))) or "C"
    alter = int(float(_text(pitch.find(_q(ns, "alter"))) or "0"))
    octave = int(_text(pitch.find(_q(ns, "octave"))) or "4")
    midi = (octave + 1) * 12 + STEP_TO_SEMITONE[step] + alter
    tonic = KEY_TO_TONIC.get(target_key, 0)
    relative = (midi - (60 + tonic)) % 12
    octave_shift = (midi - (60 + tonic)) // 12
    if relative in MAJOR_SCALE:
        return JianpuPitch(degree=MAJOR_SCALE.index(relative) + 1, octave=octave_shift, midi=midi, step=step, alter=alter)
    if (relative + 1) % 12 in MAJOR_SCALE:
        return JianpuPitch(
            degree=MAJOR_SCALE.index((relative + 1) % 12) + 1,
            octave=octave_shift,
            accidental=-1,
            midi=midi,
            step=step,
            alter=alter,
        )
    return JianpuPitch(
        degree=MAJOR_SCALE.index((relative - 1) % 12) + 1,
        octave=octave_shift,
        accidental=1,
        midi=midi,
        step=step,
        alter=alter,
    )


def _event_to_token(event: Event) -> str:
    suffix = _duration_suffix(event.duration)
    if event.kind == "rest":
        return "0" + suffix
    tokens = [_pitch_to_token(pitch) + suffix for pitch in event.pitches]
    if len(tokens) > 1:
        return "[" + "+".join(tokens) + "]"
    return tokens[0] if tokens else "?"


def _pitch_to_token(pitch: JianpuPitch) -> str:
    accidental = "#" if pitch.accidental > 0 else "b" if pitch.accidental < 0 else ""
    octave = "'" * max(0, pitch.octave) + "," * max(0, -pitch.octave)
    return f"{accidental}{pitch.degree}{octave}"


def _duration_suffix(duration: Fraction) -> str:
    if duration == Fraction(3, 2):
        return "."
    if duration == Fraction(3, 4):
        return "/."
    if duration == Fraction(3, 8):
        return "//."
    if duration >= 1:
        whole = int(duration)
        remain = duration - whole
        return "-" * max(0, whole - 1) + _duration_suffix(remain) if remain else "-" * max(0, whole - 1)
    if duration == Fraction(1, 2):
        return "/"
    if duration == Fraction(1, 4):
        return "//"
    if duration == Fraction(1, 8):
        return "///"
    return f"({duration})"


def _read_musicxml(path: Path) -> str:
    if path.suffix.lower() == ".mxl":
        with ZipFile(path) as archive:
            name = _mxl_rootfile_name(archive)
            return archive.read(name).decode("utf-8")
    return path.read_text(encoding="utf-8")


def _extract_title(root: ET.Element, ns: str) -> str:
    work_title = root.find(f"{_q(ns, 'work')}/{_q(ns, 'work-title')}")
    movement_title = root.find(_q(ns, "movement-title"))
    return _text(work_title) or _text(movement_title) or "简谱"


def _extract_part_names(root: ET.Element, ns: str) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for part_name in root.findall(f"{_q(ns, 'part-list')}/{_q(ns, 'score-part')}/{_q(ns, 'part-name')}"):
        text = _text(part_name)
        if text:
            blocks.append(TextBlock(text=text, role="instrument"))
    return blocks


def _display_measure_number(measure: ET.Element, fallback: int) -> str | int:
    raw = measure.get("number")
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return int(raw)
    except ValueError:
        return raw


def _duration_from_child(element: ET.Element, ns: str, divisions: int) -> Fraction:
    return Fraction(int(_text(element.find(_q(ns, "duration"))) or 0), divisions)


def _direction_text_blocks(direction: ET.Element, ns: str, measure_number: str | int) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    for words in direction.findall(f"{_q(ns, 'direction-type')}/{_q(ns, 'words')}"):
        text = _text(words)
        if text:
            blocks.append(TextBlock(text=text, role="expression", measure_number=measure_number))
    dynamics = direction.find(f"{_q(ns, 'direction-type')}/{_q(ns, 'dynamics')}")
    dynamic = _first_child_name(dynamics, ns)
    if dynamic:
        blocks.append(TextBlock(text=dynamic, role="expression", measure_number=measure_number))
    return blocks


def _mxl_rootfile_name(archive: ZipFile) -> str:
    try:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
    except (KeyError, ET.ParseError):
        container = None
    if container is not None:
        for rootfile in container.iter():
            if _local_name(rootfile.tag) == "rootfile":
                full_path = rootfile.get("full-path")
                if full_path:
                    return full_path
    return next(
        item
        for item in archive.namelist()
        if item.lower().endswith((".xml", ".musicxml")) and not item.startswith("META-INF/")
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


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


def _first_child_name(element: ET.Element | None, ns: str) -> str | None:
    if element is None or len(element) == 0:
        return None
    tag = element[0].tag
    return tag.removeprefix(f"{{{ns}}}") if ns else tag
