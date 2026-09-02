from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from decimal import Decimal, localcontext
from fractions import Fraction
from math import lcm

from ...models.common.types import normalize_instrument_profile
from ...models.score import Event, JianpuPitch, JianpuScore, Measure, TextBlock
from ..constants import (
    DYNAMICS,
    KEY_TO_FIFTHS,
    METRONOME_SYMBOL_TO_MUSICXML_UNIT,
    MUSICXML_METRONOME_UNIT_TO_SYMBOL,
    TOKEN_TO_MUSICXML_ACCIDENTAL,
)
from ..performance_marks import event_mark_ids, get_performance_mark
from ..pitch_spelling import jianpu_pitch_to_written


def scores_to_musicxml(
    scores: list[JianpuScore],
    title: str | None = None,
) -> str:
    rendered_scores = scores or [JianpuScore()]
    first_score = rendered_scores[0]
    instrument_profile = normalize_instrument_profile(first_score.instrument_profile)
    root = ET.Element("score-partwise", {"version": "4.0"})
    work = ET.SubElement(root, "work")
    ET.SubElement(work, "work-title").text = (
        title if title is not None else first_score.title
    ) or "Jianpu Import"
    identification = ET.SubElement(root, "identification")
    miscellaneous = ET.SubElement(identification, "miscellaneous")
    profile_field = ET.SubElement(
        miscellaneous,
        "miscellaneous-field",
        {"name": "score-trans-instrument-profile"},
    )
    profile_field.text = instrument_profile
    part_list = ET.SubElement(root, "part-list")
    for index, score in enumerate(rendered_scores, start=1):
        score_part = ET.SubElement(
            part_list,
            "score-part",
            {"id": f"P{index}"},
        )
        ET.SubElement(score_part, "part-name").text = _score_part_name(score)

    for index, score in enumerate(rendered_scores, start=1):
        part = ET.SubElement(root, "part", {"id": f"P{index}"})
        _append_score_measures(part, score, emit_tempo_map=index == 1)

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode"
    )


def _score_part_name(score: JianpuScore) -> str:
    if score.part_name:
        return score.part_name
    instrument_profile = normalize_instrument_profile(score.instrument_profile)
    return {
        "erhu": "Erhu",
        "ruan": "Ruan",
        "guzheng": "Guzheng",
    }.get(instrument_profile, "Music")


def _append_score_measures(
    part: ET.Element,
    score: JianpuScore,
    *,
    emit_tempo_map: bool,
) -> None:
    divisions = _score_divisions(score)
    previous_key: str | None = None
    previous_time: tuple[int, int] | None = None
    previous_tempo: int | None = None
    for index, source_measure in enumerate(score.measures, start=1):
        measure = ET.SubElement(part, "measure", {"number": str(index)})
        _append_print_xml(measure, source_measure)
        measure_key = getattr(source_measure, "target_key", score.target_key)
        measure_beats = getattr(source_measure, "beats_per_measure", score.beats)
        measure_beat_type = getattr(source_measure, "beat_type", score.beat_type)
        measure_time = (measure_beats, measure_beat_type)
        measure_tempo = (
            source_measure.tempo
            if source_measure.tempo is not None
            else (score.tempo if index == 1 else previous_tempo)
        )
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
        direction_blocks = _measure_direction_blocks(
            score,
            source_measure,
            measure_index=index,
            tempo=measure_tempo,
            emit_tempo=emit_tempo_map
            and measure_tempo is not None
            and (index == 1 or measure_tempo != previous_tempo),
            allow_tempo=emit_tempo_map,
        )
        _append_measure_timeline(
            measure,
            source_measure,
            direction_blocks,
            measure_key,
            divisions,
        )
        _append_barline_xml(measure, source_measure)
        previous_tempo = measure_tempo


def _score_divisions(score: JianpuScore) -> int:
    divisions = 8
    for measure in score.measures:
        for event in measure.events:
            divisions = lcm(divisions, event.duration.denominator)
            if event.start is not None:
                divisions = lcm(divisions, event.start.denominator)
        for block in measure.text_blocks:
            if block.start is not None:
                divisions = lcm(divisions, block.start.denominator)
    for block in score.text_blocks:
        if block.start is not None:
            divisions = lcm(divisions, block.start.denominator)
    return max(1, divisions)


def _append_measure_timeline(
    parent: ET.Element,
    measure: Measure,
    direction_blocks: list[TextBlock],
    measure_key: str,
    divisions: int,
) -> None:
    groups = _event_timeline_groups(measure.events)
    if not groups:
        cursor = Fraction(0, 1)
        for block in direction_blocks:
            block_start = _block_start(block)
            cursor = _append_cursor_move(parent, cursor, block_start, divisions)
            _append_direction_xml(parent, block)
        return

    emit_voice = len(groups) > 1 or any(
        event.voice is not None for event in measure.events
    )
    overall_span = max(
        (
            start + event.duration
            for events in groups.values()
            for _, event, start in events
        ),
        default=Fraction(0, 1),
    )
    overall_span = max(
        [overall_span, *(_block_start(block) for block in direction_blocks)]
    )
    cursor = Fraction(0, 1)
    for group_index, ((staff, voice), events) in enumerate(groups.items()):
        output_voice = voice if emit_voice else None
        if group_index:
            cursor = _append_cursor_move(parent, cursor, Fraction(0, 1), divisions)

        timeline: list[tuple[Fraction, int, int, Event | TextBlock]] = [
            (start, 1, source_index, event) for source_index, event, start in events
        ]
        if group_index == 0:
            timeline.extend(
                (_block_start(block), 0, block_index, block)
                for block_index, block in enumerate(direction_blocks)
            )
        timeline.sort(key=lambda item: (item[0], item[1], item[2]))

        group_span = Fraction(0, 1)
        for start, _, _, item in timeline:
            cursor = _append_cursor_move(
                parent,
                cursor,
                start,
                divisions,
                voice=output_voice,
                staff=staff,
            )
            if isinstance(item, TextBlock):
                _append_direction_xml(parent, item)
                group_span = max(group_span, start)
                continue
            _append_event_xml(
                parent,
                item,
                measure_key,
                divisions,
                suppress_dynamic=_has_matching_direction(
                    item,
                    start,
                    direction_blocks,
                ),
                output_voice=output_voice,
                output_staff=item.staff or staff,
            )
            cursor = start + item.duration
            group_span = max(group_span, cursor)
        cursor = _append_cursor_move(
            parent,
            cursor,
            group_span,
            divisions,
            voice=output_voice,
            staff=staff,
        )

    last_staff, last_voice = next(reversed(groups))
    _append_cursor_move(
        parent,
        cursor,
        overall_span,
        divisions,
        voice=last_voice if emit_voice else None,
        staff=last_staff,
    )


def _event_timeline_groups(
    events: list[Event],
) -> dict[tuple[str | None, str], list[tuple[int, Event, Fraction]]]:
    groups: dict[
        tuple[str | None, str],
        list[tuple[int, Event, Fraction]],
    ] = {}
    group_ends: dict[tuple[str | None, str], Fraction] = {}
    first_key: tuple[str | None, str] | None = None
    for source_index, event in enumerate(events):
        if (
            event.generated
            and event.voice is None
            and event.staff is None
            and first_key is not None
        ):
            key = first_key
        else:
            key = (event.staff, event.voice or "1")
        if first_key is None:
            first_key = key
        start = (
            event.start
            if event.start is not None
            else group_ends.get(key, Fraction(0, 1))
        )
        groups.setdefault(key, []).append((source_index, event, start))
        group_ends[key] = max(
            group_ends.get(key, Fraction(0, 1)), start + event.duration
        )
    return groups


def _append_cursor_move(
    parent: ET.Element,
    cursor: Fraction,
    target: Fraction,
    divisions: int,
    *,
    voice: str | None = None,
    staff: str | None = None,
) -> Fraction:
    if target == cursor:
        return cursor
    if target < cursor:
        move = ET.SubElement(parent, "backup")
        duration = cursor - target
    else:
        move = ET.SubElement(parent, "forward")
        duration = target - cursor
    ET.SubElement(move, "duration").text = str(max(1, int(duration * divisions)))
    if target > cursor:
        if voice:
            ET.SubElement(move, "voice").text = voice
        if staff:
            ET.SubElement(move, "staff").text = staff
    return target


def _has_matching_direction(
    event: Event,
    event_start: Fraction,
    blocks: list[TextBlock],
) -> bool:
    return bool(
        event.dynamic
        and any(
            block.direction_kind == "dynamics"
            and block.text == event.dynamic
            and _block_start(block) == event_start
            for block in blocks
        )
    )


def _measure_direction_blocks(
    score: JianpuScore,
    measure: Measure,
    *,
    measure_index: int,
    tempo: int | None,
    emit_tempo: bool,
    allow_tempo: bool,
) -> list[TextBlock]:
    blocks = [
        block
        for block in measure.text_blocks
        if block.role not in {"measure_number", "lyric", "title"}
        and block.text.strip()
        and (allow_tempo or block.direction_kind != "metronome")
    ]
    if measure_index == 1:
        blocks = [
            *(
                block
                for block in score.text_blocks
                if block.role != "title" and block.text.strip()
            ),
            *blocks,
        ]
    if (
        emit_tempo
        and tempo is not None
        and not any(block.direction_kind == "metronome" for block in blocks)
    ):
        blocks.insert(
            0,
            TextBlock(
                text=f"♩={tempo}",
                role="expression",
                start=Fraction(0, 1),
                placement="above",
                direction_kind="metronome",
            ),
        )
    return sorted(blocks, key=_block_start)


def _block_start(block: TextBlock) -> Fraction:
    return block.start if block.start is not None else Fraction(0, 1)


def _append_direction_xml(parent: ET.Element, block: TextBlock) -> None:
    attributes = {"placement": block.placement} if block.placement else {}
    direction = ET.SubElement(parent, "direction", attributes)
    direction_type = ET.SubElement(direction, "direction-type")
    kind = block.direction_kind or "words"
    sound_tempo: str | None = None
    if kind == "dynamics" and block.text in DYNAMICS:
        dynamics = ET.SubElement(direction_type, "dynamics")
        ET.SubElement(dynamics, block.text)
    elif kind == "rehearsal":
        ET.SubElement(direction_type, "rehearsal").text = block.text
    elif kind == "metronome":
        match = re.fullmatch(
            r"(.+?)(\.*)=(\d+(?:\.\d+)?)",
            block.text.strip(),
        )
        unit_token = match.group(1) if match else ""
        beat_unit = METRONOME_SYMBOL_TO_MUSICXML_UNIT.get(
            unit_token,
            unit_token if unit_token in MUSICXML_METRONOME_UNIT_TO_SYMBOL else None,
        )
        if match and beat_unit is not None:
            metronome = ET.SubElement(direction_type, "metronome")
            ET.SubElement(metronome, "beat-unit").text = beat_unit
            for _dot in match.group(2):
                ET.SubElement(metronome, "beat-unit-dot")
            ET.SubElement(metronome, "per-minute").text = match.group(3)
            sound_tempo = match.group(3)
        else:
            ET.SubElement(direction_type, "words").text = block.text
    elif kind in {"wedge", "pedal", "octave-shift"} and block.direction_attributes.get(
        "type"
    ):
        ET.SubElement(direction_type, kind, dict(block.direction_attributes))
    else:
        ET.SubElement(direction_type, "words").text = block.text
    if block.staff:
        ET.SubElement(direction, "staff").text = block.staff
    if sound_tempo is not None:
        ET.SubElement(direction, "sound", {"tempo": sound_tempo})


def _append_print_xml(parent: ET.Element, measure: Measure) -> None:
    attributes: dict[str, str] = {}
    if getattr(measure, "new_page", False):
        attributes["new-page"] = "yes"
    if getattr(measure, "new_system", False):
        attributes["new-system"] = "yes"
    if attributes:
        ET.SubElement(parent, "print", attributes)


def _append_barline_xml(parent: ET.Element, measure: Measure) -> None:
    ending_start = getattr(measure, "ending_start", None)
    if measure.repeat_start or ending_start is not None:
        barline = ET.SubElement(parent, "barline", {"location": "left"})
        if ending_start is not None:
            ET.SubElement(
                barline,
                "ending",
                {"number": ending_start, "type": "start"},
            )
        if measure.repeat_start:
            ET.SubElement(barline, "repeat", {"direction": "forward"})

    ending_stop = getattr(measure, "ending_stop", None)
    ending_discontinue = getattr(measure, "ending_discontinue", None)
    if measure.repeat_end or ending_stop is not None or ending_discontinue is not None:
        barline = ET.SubElement(parent, "barline", {"location": "right"})
        if ending_stop is not None:
            ET.SubElement(
                barline,
                "ending",
                {"number": ending_stop, "type": "stop"},
            )
        if ending_discontinue is not None:
            ET.SubElement(
                barline,
                "ending",
                {"number": ending_discontinue, "type": "discontinue"},
            )
        if measure.repeat_end:
            repeat_attributes = {"direction": "backward"}
            if measure.repeat_count > 1:
                repeat_attributes["times"] = str(measure.repeat_count)
            ET.SubElement(barline, "repeat", repeat_attributes)


def _append_event_xml(
    parent: ET.Element,
    event: Event,
    measure_key: str,
    divisions: int,
    *,
    suppress_dynamic: bool = False,
    output_voice: str | None = None,
    output_staff: str | None = None,
) -> None:
    pitches = event.pitches or [None]
    for index, pitch in enumerate(pitches):
        note = ET.SubElement(parent, "note")
        if index > 0:
            ET.SubElement(note, "chord")
        if event.kind == "rest" or pitch is None:
            rest_attributes = {"measure": "yes"} if event.measure_rest else {}
            ET.SubElement(note, "rest", rest_attributes)
            written_alter: Fraction | None = None
        else:
            written_alter = _append_pitch_xml(note, pitch, measure_key)
        duration_units = max(1, int(event.duration * divisions))
        ET.SubElement(note, "duration").text = str(duration_units)
        if event.tie_start:
            ET.SubElement(note, "tie", {"type": "start"})
        if event.tie_stop:
            ET.SubElement(note, "tie", {"type": "stop"})
        if output_voice:
            ET.SubElement(note, "voice").text = output_voice
        note_type, dot_count = _fraction_to_type(_notated_duration(event))
        ET.SubElement(note, "type").text = note_type
        for _dot in range(dot_count):
            ET.SubElement(note, "dot")
        if index == 0:
            seen_beams: set[tuple[str, str]] = set()
            for beam in event.beams:
                key = (beam.number, beam.status)
                if key in seen_beams:
                    continue
                seen_beams.add(key)
                ET.SubElement(
                    note,
                    "beam",
                    {"number": beam.number},
                ).text = beam.status
        if (
            pitch is not None
            and pitch.accidental_text is not None
            and written_alter is not None
        ):
            accidental_name = _musicxml_accidental_name(
                pitch.accidental_text,
                written_alter,
            )
            if accidental_name is not None:
                ET.SubElement(note, "accidental").text = accidental_name
        if event.tuplet_count:
            normal_notes = event.tuplet_normal_count or _tuplet_normal_notes(
                event.tuplet_count
            )
            if normal_notes != event.tuplet_count:
                time_mod = ET.SubElement(note, "time-modification")
                ET.SubElement(time_mod, "actual-notes").text = str(event.tuplet_count)
                ET.SubElement(time_mod, "normal-notes").text = str(normal_notes)
        if output_staff:
            ET.SubElement(note, "staff").text = output_staff
        if index == 0:
            _append_notations(note, event, suppress_dynamic=suppress_dynamic)
        if event.lyric and index == 0:
            lyric = ET.SubElement(note, "lyric")
            ET.SubElement(lyric, "text").text = event.lyric


def _append_notations(
    note: ET.Element,
    event: Event,
    *,
    suppress_dynamic: bool = False,
) -> None:
    articulations = list(
        event.articulations or ([event.articulation] if event.articulation else [])
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
            event.tuplet_spans,
            event.dynamic if not suppress_dynamic else None,
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
    if event.tuplet_spans:
        for span in event.tuplet_spans:
            if span.start:
                ET.SubElement(
                    notations,
                    "tuplet",
                    {"type": "start", "number": span.number},
                )
        for span in reversed(event.tuplet_spans):
            if span.stop:
                ET.SubElement(
                    notations,
                    "tuplet",
                    {"type": "stop", "number": span.number},
                )
    else:
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

    if event.dynamic and not suppress_dynamic:
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
) -> Fraction:
    step, alter, octave = jianpu_pitch_to_written(
        pitch_value.degree,
        pitch_value.accidental,
        pitch_value.octave,
        measure_key,
    )
    # 还原号(n/♮)语义：把调号里的升降取消，用自然音。jianpu_pitch_to_written 会把
    # accidental=0 当成"无升降"而叠加调号(key_alter)，导致还原号被错误映射回升/降音。
    # 这里显式将还原号的 alter 归 0，确保写出自然音(不写 <alter>，且 _musicxml_accidental_name
    # 会据此输出 <accidental>natural</accidental>)。
    if pitch_value.accidental_text in {"♮", "n"}:
        alter = Fraction(0)
    pitch = ET.SubElement(note, "pitch")
    ET.SubElement(pitch, "step").text = step
    if alter:
        ET.SubElement(pitch, "alter").text = _fraction_to_decimal_text(alter)
    ET.SubElement(pitch, "octave").text = str(octave)
    return alter


def _musicxml_accidental_name(
    accidental_text: str,
    written_alter: Fraction,
) -> str | None:
    token = {
        Fraction(-2, 1): "bb",
        Fraction(-3, 2): "tqf",
        Fraction(-1, 1): "b",
        Fraction(-1, 2): "qf",
        Fraction(0, 1): "n",
        Fraction(1, 2): "qs",
        Fraction(1, 1): "#",
        Fraction(3, 2): "tqs",
        Fraction(2, 1): "x",
    }.get(written_alter)
    if token is None:
        return None
    if accidental_text in {"♮", "n"} and written_alter == 0:
        token = "n"
    return TOKEN_TO_MUSICXML_ACCIDENTAL.get(token)


def _fraction_to_decimal_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    with localcontext() as context:
        context.prec = max(
            28,
            len(str(abs(value.numerator))) + len(str(value.denominator)) + 4,
        )
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
    return format(decimal_value, "f").rstrip("0").rstrip(".")


def _fraction_to_type(duration: Fraction) -> tuple[str, int]:
    base = {
        Fraction(4, 1): "whole",
        Fraction(2, 1): "half",
        Fraction(1, 1): "quarter",
        Fraction(1, 2): "eighth",
        Fraction(1, 4): "16th",
        Fraction(1, 8): "32nd",
    }
    if duration in base:
        return base[duration], 0
    for value, name in base.items():
        for dot_count in range(1, 4):
            multiplier = Fraction((1 << (dot_count + 1)) - 1, 1 << dot_count)
            if duration == value * multiplier:
                return name, dot_count
    return "quarter", 0


def _notated_duration(event: Event) -> Fraction:
    if not event.tuplet_count:
        return event.duration
    normal_notes = event.tuplet_normal_count or _tuplet_normal_notes(event.tuplet_count)
    return event.duration * Fraction(event.tuplet_count, normal_notes)


def _tuplet_normal_notes(actual_notes: int) -> int:
    normal_notes = 1
    while normal_notes * 2 <= actual_notes:
        normal_notes *= 2
    return max(1, normal_notes)
