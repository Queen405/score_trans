from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
import re

from ..constants import FIFTHS_TO_KEY, KEY_TO_TONIC, MAJOR_SCALE, STEP_TO_SEMITONE
from ..performance_marks import canonical_mark_id, normalize_event_marks
from ..xml_utils import (
    _namespace,
    _q,
    _local_name,
    _text,
    _read_musicxml,
)
from ...models.common.types import (
    ACCEPTED_INSTRUMENT_PROFILES,
    InstrumentProfile,
    normalize_instrument_profile,
)
from ...models.score import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock

_PROVENANCE_PART_RE = re.compile(
    r"(?:^|__)(?P<role>[a-z]+)\d*-s(?P<sheet>\d+)-i(?P<inter>\d+)"
)


def musicxml_path_to_scores(
    path: Path,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> list[JianpuScore]:
    return musicxml_to_scores(
        _read_musicxml(path),
        target_key,
        start_measure_number,
        title,
        instrument_profile,
    )


def read_musicxml_text(path: Path) -> str:
    return _read_musicxml(path)


def musicxml_to_scores(
    xml_text: str,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> list[JianpuScore]:
    if target_key not in KEY_TO_TONIC:
        raise ValueError(f"不支持的简谱调：{target_key}")

    root = ET.fromstring(xml_text)
    ns = _namespace(root.tag)
    xml_parts = root.findall(_q(ns, "part"))
    if not xml_parts:
        return [JianpuScore(title=title or "简谱", target_key=target_key)]

    extracted_title = title or _extract_title(root, ns)
    profile = (
        normalize_instrument_profile(instrument_profile)
        if instrument_profile
        else _extract_instrument_profile(root, ns)
    )
    part_names = _extract_part_names(root, ns)

    raw_scores: list[JianpuScore] = []
    for part_element in xml_parts:
        part_id = part_element.get("id", "")
        part_name = part_names.get(part_id, "")
        score = _parse_single_part(
            part_element,
            ns,
            target_key,
            start_measure_number,
            extracted_title,
            profile,
        )
        score.part_name = part_name
        raw_scores.append(score)

    final_scores: list[JianpuScore] = []
    for raw_score in raw_scores:
        staff_scores = _split_part_by_staff(raw_score)
        final_scores.extend(staff_scores)

    part_count = len(final_scores)
    for index, score in enumerate(final_scores):
        score.part_index = index
        score.part_count = part_count
        if not score.part_name:
            score.part_name = f"声部{index + 1}"

    return final_scores


def musicxml_path_to_score(
    path: Path,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> JianpuScore:
    scores = musicxml_path_to_scores(
        path,
        target_key=target_key,
        start_measure_number=start_measure_number,
        title=title,
        instrument_profile=instrument_profile,
    )
    return (
        scores[0]
        if scores
        else JianpuScore(title=title or "简谱", target_key=target_key)
    )


def musicxml_to_score(
    xml_text: str,
    target_key: str = "C",
    start_measure_number: int | None = None,
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> JianpuScore:
    scores = musicxml_to_scores(
        xml_text,
        target_key=target_key,
        start_measure_number=start_measure_number,
        title=title,
        instrument_profile=instrument_profile,
    )
    return (
        scores[0]
        if scores
        else JianpuScore(title=title or "简谱", target_key=target_key)
    )


def _parse_single_part(
    part: ET.Element,
    ns: str,
    target_key: str,
    start_measure_number: int | None,
    extracted_title: str,
    instrument_profile: InstrumentProfile,
) -> JianpuScore:
    score = JianpuScore(
        title=extracted_title,
        target_key=target_key,
        instrument_profile=instrument_profile,
    )
    if extracted_title:
        score.text_blocks.append(TextBlock(text=extracted_title, role="title"))
    current_key = "C"
    current_beats = 4
    current_beat_type = 4
    divisions = 1
    initialized_score_time = False

    for index, xml_measure in enumerate(part.findall(_q(ns, "measure")), start=1):
        attrs = xml_measure.find(_q(ns, "attributes"))
        if attrs is not None:
            divisions = int(_text(attrs.find(_q(ns, "divisions"))) or divisions)
            fifths = _text(attrs.find(f"{_q(ns, 'key')}/{_q(ns, 'fifths')}"))
            if fifths is not None:
                current_key = FIFTHS_TO_KEY.get(int(fifths), "C")
            beats_text = _text(attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beats')}"))
            beat_type_text = _text(
                attrs.find(f"{_q(ns, 'time')}/{_q(ns, 'beat-type')}")
            )
            if beats_text and beat_type_text:
                current_beats = int(beats_text)
                current_beat_type = int(beat_type_text)
                if not initialized_score_time:
                    score.beats = current_beats
                    score.beat_type = current_beat_type
                    initialized_score_time = True
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
        measure.text_blocks.append(
            TextBlock(
                text=str(display_number),
                role="measure_number",
                measure_number=display_number,
            )
        )
        _read_measure_events(xml_measure, ns, divisions, target_key, measure)
        _normalize_measure(measure, current_beats, current_beat_type)
        score.measures.append(measure)

    _restore_slide_directions(score)
    return score


def _extract_part_names(root: ET.Element, ns: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for score_part in root.findall(f"{_q(ns, 'part-list')}/{_q(ns, 'score-part')}"):
        part_id = score_part.get("id", "")
        part_name = _text(score_part.find(_q(ns, "part-name")))
        if part_name:
            names[part_id] = part_name.strip()
    return names


def _split_part_by_staff(score: JianpuScore) -> list[JianpuScore]:
    staff_values: set[str] = set()
    for measure in score.measures:
        for event in measure.events:
            if event.staff:
                staff_values.add(event.staff)
    if len(staff_values) <= 1:
        return [score]

    sorted_staffs = sorted(staff_values, key=lambda s: int(s) if s.isdigit() else s)
    results: list[JianpuScore] = []
    for staff_index, staff in enumerate(sorted_staffs):
        staff_score = JianpuScore(
            title=score.title,
            target_key=score.target_key,
            source_key=score.source_key,
            beats=score.beats,
            beat_type=score.beat_type,
            instrument_profile=score.instrument_profile,
            part_name=score.part_name,
        )
        for measure in score.measures:
            staff_events = [
                event
                for event in measure.events
                if event.staff == staff
                or (event.staff is None and not event.generated and staff_index == 0)
            ]
            staff_measure = Measure(
                source_number=measure.source_number,
                display_measure_number=measure.display_measure_number,
                duration=measure.duration,
                beats_per_measure=measure.beats_per_measure,
                beat_type=measure.beat_type,
                source_key=measure.source_key,
                target_key=measure.target_key,
                repeat_start=measure.repeat_start,
                repeat_end=measure.repeat_end,
                repeat_count=measure.repeat_count,
                source_page_index=measure.source_page_index,
            )
            staff_measure.events = staff_events
            staff_measure.text_blocks = [
                block
                for block in measure.text_blocks
                if block.role != "lyric"
                and (block.staff is None or block.staff == staff)
            ]
            _normalize_measure(
                staff_measure, staff_measure.beats_per_measure, staff_measure.beat_type
            )
            staff_score.measures.append(staff_measure)
        staff_score.part_name = (
            f"{score.part_name}(staff {staff})" if score.part_name else f"staff {staff}"
        )
        results.append(staff_score)
    return results if results else [score]


def _extract_title(root: ET.Element, ns: str) -> str:
    work_title = root.find(f"{_q(ns, 'work')}/{_q(ns, 'work-title')}")
    movement_title = root.find(_q(ns, "movement-title"))
    return _text(work_title) or _text(movement_title) or "简谱"


def _extract_instrument_profile(root: ET.Element, ns: str) -> InstrumentProfile:
    for field in root.findall(f".//{_q(ns, 'miscellaneous-field')}"):
        name = (field.get("name") or "").strip().lower()
        value = (_text(field) or "").strip().lower()
        if (
            name
            in {
                "score-trans-instrument-profile",
                "score-trans:instrument-profile",
            }
            and value in ACCEPTED_INSTRUMENT_PROFILES
        ):
            return normalize_instrument_profile(value)
    part_name = _text(
        root.find(f"{_q(ns, 'part-list')}/{_q(ns, 'score-part')}/{_q(ns, 'part-name')}")
    )
    normalized = (part_name or "").strip().lower()
    if normalized in {"二胡", "erhu"}:
        return "erhu"
    if normalized in {"阮", "中阮", "ruan", "zhongruan", "zhong ruan"}:
        return "ruan"
    if normalized in {"古筝", "guzheng", "zheng"}:
        return "guzheng"
    return "general"


def _display_measure_number(measure: ET.Element, fallback: int) -> str | int:
    raw = measure.get("number")
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return int(raw)
    except ValueError:
        return raw


def _read_measure_events(
    xml_measure: ET.Element,
    ns: str,
    divisions: int,
    target_key: str,
    measure: Measure,
) -> None:
    last_event: Event | None = None
    cursor = Fraction(0, 1)
    pending_dynamics: list[tuple[Fraction, str]] = []
    active_tuplets: dict[str, str] = {}
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
            blocks = _direction_text_blocks(
                child, ns, measure.display_measure_number, cursor
            )
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

        if (
            note.find(_q(ns, "chord")) is not None
            and last_event is not None
            and last_event.kind == "note"
        ):
            pitch = _note_pitch(note, ns, target_key)
            if pitch:
                provenance = _note_provenance(note)
                pitch.source_id = _first_source(provenance, "note")
                pitch.accidental_source_id = _first_source(provenance, "accidental")
                last_event.pitches.append(pitch)
                last_event.pitches.sort(key=lambda value: value.rank, reverse=True)
                _merge_event_provenance(last_event, provenance)
            continue

        if note.find(_q(ns, "rest")) is not None:
            event = Event(kind="rest", duration=duration)
        else:
            pitch = _note_pitch(note, ns, target_key)
            event = Event(
                kind="note", duration=duration, pitches=[pitch] if pitch else []
            )
        provenance = _note_provenance(note)
        if event.kind == "note" and event.pitches:
            event.pitches[0].source_id = _first_source(provenance, "note")
            event.pitches[0].accidental_source_id = _first_source(
                provenance, "accidental"
            )
        _merge_event_provenance(event, provenance)
        event.dotted = len(note.findall(_q(ns, "dot")))
        event.tie_start = any(
            tie.get("type") == "start" for tie in note.findall(_q(ns, "tie"))
        )
        event.tie_stop = any(
            tie.get("type") == "stop" for tie in note.findall(_q(ns, "tie"))
        )
        event.voice = _text(note.find(_q(ns, "voice")))
        event.staff = _text(note.find(_q(ns, "staff")))
        event.start = cursor
        notations = note.find(_q(ns, "notations"))
        if notations is not None:
            event.slur_start = any(
                slur.get("type") == "start"
                for slur in notations.findall(_q(ns, "slur"))
            )
            event.slur_stop = any(
                slur.get("type") == "stop" for slur in notations.findall(_q(ns, "slur"))
            )
            event.slide_start = any(
                slide.get("type") == "start"
                for slide in notations.findall(_q(ns, "slide"))
            )
            event.slide_stop = any(
                slide.get("type") == "stop"
                for slide in notations.findall(_q(ns, "slide"))
            )
            event.articulations = _notation_marks(
                notations.find(_q(ns, "articulations")), ns
            )
            if notations.find(_q(ns, "fermata")) is not None:
                event.articulations.insert(0, "fermata")
            event.articulation = event.articulations[0] if event.articulations else None
            event.ornaments = _notation_marks(notations.find(_q(ns, "ornaments")), ns)
            event.technical = _notation_marks(notations.find(_q(ns, "technical")), ns)
            if notations.find(_q(ns, "arpeggiate")) is not None:
                event.technical.append("arpeggio")
            event.dynamic = _dynamic_text(notations.find(_q(ns, "dynamics")), ns)
            _apply_tuplet_notations(
                event, notations, ns, measure.source_number, cursor, active_tuplets
            )
            normalize_event_marks(event)
        time_modification = note.find(_q(ns, "time-modification"))
        if time_modification is not None:
            actual_notes = _text(time_modification.find(_q(ns, "actual-notes")))
            if actual_notes and actual_notes.isdigit():
                event.tuplet_count = int(actual_notes)
                if event.tuplet_id is None and active_tuplets:
                    event.tuplet_id = next(reversed(active_tuplets.values()))
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


def _note_provenance(note: ET.Element) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    xml_id = note.get("id") or ""
    for match in _PROVENANCE_PART_RE.finditer(xml_id):
        role = _source_role(match.group("role"))
        source_id = f"s{match.group('sheet')}:i{match.group('inter')}"
        result.setdefault(role, []).append(source_id)
    return result


def _source_role(code: str) -> str:
    return {
        "n": "note",
        "a": "accidental",
        "ss": "slur_start",
        "se": "slur_stop",
        "ar": "articulation",
        "or": "ornament",
        "dy": "dynamic",
        "bo": "technical",
        "fi": "technical",
        "pl": "technical",
        "ap": "technical",
        "pa": "articulation",
        "fe": "articulation",
        "tu": "tuplet",
    }.get(code, code)


def _first_source(provenance: dict[str, list[str]], role: str) -> str | None:
    sources = provenance.get(role, [])
    return sources[0] if sources else None


def _merge_event_provenance(event: Event, provenance: dict[str, list[str]]) -> None:
    for role, sources in provenance.items():
        target = event.source_roles.setdefault(role, [])
        for source_id in sources:
            if source_id not in target:
                target.append(source_id)
            if source_id not in event.source_ids:
                event.source_ids.append(source_id)


def _restore_slide_directions(score: JianpuScore) -> None:
    open_slide: Event | None = None
    for measure in score.measures:
        for event in measure.events:
            if event.slide_stop and open_slide is not None:
                _infer_slide_direction(open_slide, event)
                open_slide = None
            if event.slide_start:
                open_slide = event


def _infer_slide_direction(start: Event, stop: Event) -> None:
    if len(start.pitches) != 1 or len(stop.pitches) != 1:
        return
    start_rank = start.pitches[0].rank
    stop_rank = stop.pitches[0].rank
    if start_rank == stop_rank:
        return
    direction = "up" if stop_rank > start_rank else "down"
    start.slide_direction = direction
    stop.slide_direction = direction


def _apply_tuplet_notations(
    event: Event,
    notations: ET.Element,
    ns: str,
    measure_number: str,
    cursor: Fraction,
    active_tuplets: dict[str, str],
) -> None:
    for tuplet in notations.findall(_q(ns, "tuplet")):
        number = tuplet.get("number") or "1"
        kind = tuplet.get("type")
        if kind == "start":
            group_id = f"{measure_number}:{number}:{cursor}"
            active_tuplets[number] = group_id
            event.tuplet_id = group_id
            event.tuplet_start = True
        elif number in active_tuplets:
            event.tuplet_id = active_tuplets[number]
        if kind == "stop":
            event.tuplet_id = event.tuplet_id or active_tuplets.get(number)
            event.tuplet_stop = True
            active_tuplets.pop(number, None)


def _normalize_measure(measure: Measure, beats: int, beat_type: int) -> None:
    target = Fraction(beats * 4, beat_type)
    actual = measure.span_duration
    if actual < target:
        measure.events.append(
            Event(kind="rest", duration=target - actual, start=actual, generated=True)
        )
    elif actual > target:
        measure.validation_errors.append(f"小节超拍：实际 {actual}，目标 {target}")

    beat_duration = Fraction(4, beat_type)
    measure.duration = target
    measure.beats_per_measure = beats
    measure.beat_type = beat_type
    measure.beats = [
        Beat(index=index + 1, duration=beat_duration, start=index * beat_duration)
        for index in range(beats)
    ]
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
    tonic = KEY_TO_TONIC[target_key]
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
                blocks.append(
                    _measure_text_block(
                        text,
                        measure_number,
                        start,
                        words.get("placement") or placement,
                        staff,
                    )
                )

        for rehearsal in direction_type.findall(_q(ns, "rehearsal")):
            text = _text(rehearsal)
            if text:
                blocks.append(
                    _measure_text_block(text, measure_number, start, placement, staff)
                )

        dynamics = direction_type.find(_q(ns, "dynamics"))
        dynamic = _dynamic_text(dynamics, ns)
        if dynamic:
            blocks.append(
                _measure_text_block(
                    dynamic,
                    measure_number,
                    start,
                    dynamics.get("placement") or placement,
                    staff,
                )
            )

        metronome = direction_type.find(_q(ns, "metronome"))
        metronome_text = _metronome_text(metronome, ns)
        if metronome_text:
            blocks.append(
                _measure_text_block(
                    metronome_text, measure_number, start, placement, staff
                )
            )

        wedge = direction_type.find(_q(ns, "wedge"))
        if wedge is not None:
            wedge_text = _wedge_text(wedge.get("type"))
            if wedge_text:
                blocks.append(
                    _measure_text_block(
                        wedge_text, measure_number, start, placement, staff
                    )
                )

        pedal = direction_type.find(_q(ns, "pedal"))
        if pedal is not None:
            pedal_text = _pedal_text(pedal.get("type"))
            if pedal_text:
                blocks.append(
                    _measure_text_block(
                        pedal_text, measure_number, start, placement, staff
                    )
                )

        octave_shift = direction_type.find(_q(ns, "octave-shift"))
        if octave_shift is not None:
            shift_text = _octave_shift_text(
                octave_shift.get("type"), octave_shift.get("size")
            )
            if shift_text:
                blocks.append(
                    _measure_text_block(
                        shift_text, measure_number, start, placement, staff
                    )
                )

        for child in list(direction_type):
            name = _local_name(child.tag)
            if name in {
                "words",
                "rehearsal",
                "dynamics",
                "metronome",
                "wedge",
                "pedal",
                "octave-shift",
            }:
                continue
            text = _text(child) or _direction_symbol_text(name)
            if text:
                blocks.append(
                    _measure_text_block(text, measure_number, start, placement, staff)
                )
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


def _pending_dynamic_for_event(
    pending_dynamics: list[tuple[Fraction, str]], cursor: Fraction
) -> str | None:
    for start, dynamic in pending_dynamics:
        if start <= cursor:
            return dynamic
    return None


def _notation_marks(element: ET.Element | None, ns: str) -> list[str]:
    if element is None:
        return []
    marks: list[str] = []
    section = _local_name(element.tag)
    for child in list(element):
        name = _local_name(child.tag)
        text = _text(child)
        if section == "ornaments" and name == "wavy-line":
            continue
        if section == "technical" and name == "harmonic":
            if child.find(_q(ns, "artificial")) is not None:
                marks.append("artificial-harmonic")
            else:
                marks.append("natural-harmonic")
        elif text and name == "fingering" and text.strip() in {"1", "2", "3", "4"}:
            marks.append(f"fingering-{text.strip()}")
        elif text and name in {"string", "fret"}:
            marks.append(text)
        elif text and name in {
            "other-technical",
            "other-ornament",
            "other-articulation",
        }:
            marks.append(text)
        else:
            marks.append(name)
    result: list[str] = []
    for mark in marks:
        mark_id = canonical_mark_id(mark)
        resolved = mark_id or mark
        if resolved and resolved not in result:
            result.append(resolved)
    return result


def _dynamic_text(dynamics: ET.Element | None, ns: str) -> str | None:
    if dynamics is None or len(dynamics) == 0:
        return None
    child = dynamics[0]
    text = _text(child)
    if text:
        return text
    return (
        _local_name(child.tag).removeprefix(f"{{{ns}}}")
        if ns
        else _local_name(child.tag)
    )


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
    return text in {
        "p",
        "pp",
        "ppp",
        "pppp",
        "f",
        "ff",
        "fff",
        "ffff",
        "mp",
        "mf",
        "sf",
        "sfz",
        "sfp",
        "fp",
        "fz",
        "rfz",
    }


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
