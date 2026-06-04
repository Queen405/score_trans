from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from zipfile import ZipFile

from .jianpu_tokens import duration_affixes
from .jianpu import FIFTHS_TO_KEY, KEY_TO_TONIC, MAJOR_SCALE, STEP_TO_SEMITONE
from ..models.score import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock


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
    lines = [f"1={score.target_key}", f"{score.beats}/{score.beat_type}"]
    if score.title and score.title != "简谱":
        lines.insert(0, f"title={score.title}")
    measures = []
    lyrics: list[str] = []
    for measure in score.measures:
        events = measure.events
        tokens = []
        for event in events:
            if event.dynamic:
                tokens.append(f"\\{event.dynamic}")
            for articulation in event.articulations or ([event.articulation] if event.articulation else []):
                mark = _articulation_token(articulation)
                if mark:
                    tokens.append(f"^{mark}")
            tokens.append(_event_to_token(event))
            if event.lyric:
                lyrics.append(event.lyric)
        prefix = "|: " if getattr(measure, "repeat_start", False) else ""
        suffix = " :|" if getattr(measure, "repeat_end", False) else ""
        measures.append(prefix + " ".join(tokens) + suffix)
    lines.append(" | ".join(measures) + (" |" if measures else ""))
    if lyrics:
        lines.append(f"L: {' '.join(lyrics)}")
    text_lines = [_text_block_to_directive(block) for block in score.text_blocks if block.text.strip()]
    if text_lines:
        lines.append("")
        lines.extend(text_lines)
    return "\n".join(lines)


def _text_block_to_directive(block: TextBlock) -> str:
    text = " ".join(block.text.split())
    role = block.role or "other"
    if block.bbox is None:
        return f"@text - - - - {role} {text}"
    x1, y1, x2, y2 = block.bbox
    return f"@text {_fmt_num(x1)} {_fmt_num(y1)} {_fmt_num(x2)} {_fmt_num(y2)} {role} {text}"


def _fmt_num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _read_measure_events(xml_measure: ET.Element, ns: str, divisions: int, target_key: str, measure: Measure) -> None:
    last_event: Event | None = None
    cursor = Fraction(0, 1)
    pending_dynamics: list[tuple[Fraction, str]] = []
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
            blocks = _direction_text_blocks(child, ns, measure.display_measure_number, cursor)
            measure.text_blocks.extend(blocks)
            pending_dynamics.extend(
                (cursor, block.text.strip())
                for block in blocks
                if block.text and _is_dynamic_name(block.text.strip())
            )
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
            event.articulations = _notation_marks(notations.find(_q(ns, "articulations")), ns)
            if notations.find(_q(ns, "fermata")) is not None:
                event.articulations.insert(0, "fermata")
            event.articulation = event.articulations[0] if event.articulations else None
            event.ornaments = _notation_marks(notations.find(_q(ns, "ornaments")), ns)
            event.technical = _notation_marks(notations.find(_q(ns, "technical")), ns)
            event.dynamic = _dynamic_text(notations.find(_q(ns, "dynamics")), ns)
        if event.dynamic is None:
            dynamic = _pending_dynamic_for_event(pending_dynamics, cursor)
            if dynamic:
                event.dynamic = dynamic
                pending_dynamics = [
                    pending
                    for pending in pending_dynamics
                    if not (pending[0] <= cursor and pending[1] == dynamic)
                ]
        lyric = note.find(_q(ns, "lyric"))
        if lyric is not None:
            event.lyric = _text(lyric.find(_q(ns, "text")))
            if event.lyric:
                measure.text_blocks.append(
                    TextBlock(
                        text=event.lyric,
                        role="lyric",
                        measure_number=measure.display_measure_number,
                        start=cursor,
                        placement="below",
                    )
                )
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
    accidental_text = _accidental_token(_text(note.find(_q(ns, "accidental"))))
    midi = (octave + 1) * 12 + STEP_TO_SEMITONE[step] + alter
    tonic = KEY_TO_TONIC.get(target_key, 0)
    relative = (midi - (60 + tonic)) % 12
    octave_shift = (midi - (60 + tonic)) // 12
    if relative in MAJOR_SCALE:
        return JianpuPitch(
            degree=MAJOR_SCALE.index(relative) + 1,
            octave=octave_shift,
            midi=midi,
            step=step,
            alter=alter,
            accidental_text=accidental_text,
        )
    if (relative + 1) % 12 in MAJOR_SCALE:
        return JianpuPitch(
            degree=MAJOR_SCALE.index((relative + 1) % 12) + 1,
            octave=octave_shift,
            accidental=-1,
            midi=midi,
            step=step,
            alter=alter,
            accidental_text=accidental_text,
        )
    return JianpuPitch(
        degree=MAJOR_SCALE.index((relative - 1) % 12) + 1,
        octave=octave_shift,
        accidental=1,
        midi=midi,
        step=step,
        alter=alter,
        accidental_text=accidental_text,
    )


def _event_to_token(event: Event) -> str:
    prefix, suffix = _duration_parts(event.duration)
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [_pitch_to_token(pitch) for pitch in event.pitches]
        body = "[" + "+".join(tokens) + "]" if len(tokens) > 1 else tokens[0] if tokens else "?"
    body = prefix + body + suffix
    if event.tie_stop:
        body = "~" + body
    if event.slur_start:
        body = "(" + body
    if event.slur_stop:
        body = body + ")"
    if event.tie_start:
        body = body + "~"
    return body


def _duration_parts(duration: Fraction) -> tuple[str, str]:
    return duration_affixes(duration)


def _articulation_token(name: str) -> str | None:
    return {
        "accent": ">",
        "strong-accent": ">",
        "staccato": ".",
        "tenuto": "-",
        "trill-mark": "tr",
        "fermata": "fermata",
    }.get(name, name if name else None)


def _pitch_to_token(pitch: JianpuPitch) -> str:
    accidental = pitch.accidental_text
    if accidental is None:
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


def _direction_text_blocks(
    direction: ET.Element,
    ns: str,
    measure_number: str | int,
    start: Fraction,
) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    placement = direction.get("placement")
    staff = _text(direction.find(_q(ns, "staff")))
    for direction_type in direction.findall(_q(ns, "direction-type")):
        for words in direction_type.findall(_q(ns, "words")):
            text = _text(words)
            if text:
                blocks.append(_measure_text_block(text, measure_number, start, words.get("placement") or placement, staff))

        for rehearsal in direction_type.findall(_q(ns, "rehearsal")):
            text = _text(rehearsal)
            if text:
                blocks.append(_measure_text_block(text, measure_number, start, placement, staff))

        dynamics = direction_type.find(_q(ns, "dynamics"))
        dynamic = _dynamic_text(dynamics, ns)
        if dynamic:
            blocks.append(_measure_text_block(dynamic, measure_number, start, dynamics.get("placement") or placement, staff))

        metronome = direction_type.find(_q(ns, "metronome"))
        metronome_text = _metronome_text(metronome, ns)
        if metronome_text:
            blocks.append(_measure_text_block(metronome_text, measure_number, start, placement, staff))

        wedge = direction_type.find(_q(ns, "wedge"))
        if wedge is not None:
            wedge_text = _wedge_text(wedge.get("type"))
            if wedge_text:
                blocks.append(_measure_text_block(wedge_text, measure_number, start, placement, staff))

        pedal = direction_type.find(_q(ns, "pedal"))
        if pedal is not None:
            pedal_text = _pedal_text(pedal.get("type"))
            if pedal_text:
                blocks.append(_measure_text_block(pedal_text, measure_number, start, placement, staff))

        octave_shift = direction_type.find(_q(ns, "octave-shift"))
        if octave_shift is not None:
            shift_text = _octave_shift_text(octave_shift.get("type"), octave_shift.get("size"))
            if shift_text:
                blocks.append(_measure_text_block(shift_text, measure_number, start, placement, staff))

        for child in list(direction_type):
            name = _local_name(child.tag)
            if name in {"words", "rehearsal", "dynamics", "metronome", "wedge", "pedal", "octave-shift"}:
                continue
            text = _text(child) or _direction_symbol_text(name)
            if text:
                blocks.append(_measure_text_block(text, measure_number, start, placement, staff))
    return blocks


def _measure_text_block(
    text: str,
    measure_number: str | int,
    start: Fraction,
    placement: str | None,
    staff: str | None,
) -> TextBlock:
    return TextBlock(
        text=text,
        role="expression",
        measure_number=measure_number,
        start=start,
        placement=placement,
        staff=staff,
    )


def _pending_dynamic_for_event(pending_dynamics: list[tuple[Fraction, str]], cursor: Fraction) -> str | None:
    for start, dynamic in pending_dynamics:
        if start <= cursor:
            return dynamic
    return None


def _notation_marks(element: ET.Element | None, ns: str) -> list[str]:
    if element is None:
        return []
    marks: list[str] = []
    for child in list(element):
        name = _local_name(child.tag)
        text = _text(child)
        if text and name in {"fingering", "string", "fret"}:
            marks.append(text)
        elif text and name in {"other-technical", "other-ornament", "other-articulation"}:
            marks.append(text)
        else:
            marks.append(name.removeprefix(f"{{{ns}}}") if ns else name)
    return marks


def _dynamic_text(dynamics: ET.Element | None, ns: str) -> str | None:
    if dynamics is None or len(dynamics) == 0:
        return None
    child = dynamics[0]
    text = _text(child)
    if text:
        return text
    return _local_name(child.tag).removeprefix(f"{{{ns}}}") if ns else _local_name(child.tag)


def _metronome_text(metronome: ET.Element | None, ns: str) -> str | None:
    if metronome is None:
        return None
    unit = _text(metronome.find(_q(ns, "beat-unit")))
    per_minute = _text(metronome.find(_q(ns, "per-minute")))
    if unit and per_minute:
        return f"{unit}={per_minute}"
    return _text(metronome)


def _wedge_text(kind: str | None) -> str | None:
    if kind == "crescendo":
        return "cresc."
    if kind == "diminuendo":
        return "dim."
    return None


def _pedal_text(kind: str | None) -> str | None:
    if kind == "start":
        return "Ped."
    if kind in {"stop", "discontinue"}:
        return "*"
    if kind == "change":
        return "Ped."
    return None


def _octave_shift_text(kind: str | None, size: str | None) -> str | None:
    if kind == "stop":
        return "loco"
    if kind in {"up", "down"}:
        interval = size or "8"
        return f"{interval}va" if kind == "up" else f"{interval}vb"
    return None


def _direction_symbol_text(name: str) -> str | None:
    if name in {"segno", "coda", "dacapo", "dalsegno", "tocoda", "fine"}:
        return name
    return None


def _is_dynamic_name(text: str) -> bool:
    return text in {"p", "pp", "ppp", "pppp", "f", "ff", "fff", "ffff", "mp", "mf", "sf", "sfz", "sfp", "fp", "fz", "rfz"}


def _accidental_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    return {
        "sharp": "#",
        "flat": "b",
        "natural": "n",
        "double-sharp": "x",
        "sharp-sharp": "x",
        "double-flat": "bb",
        "flat-flat": "bb",
        "quarter-flat": "b",
        "quarter-sharp": "#",
        "three-quarters-flat": "b",
        "three-quarters-sharp": "#",
    }.get(normalized)


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
