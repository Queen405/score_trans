from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast

from ...models.common.types import (
    ACCEPTED_INSTRUMENT_PROFILES,
    InstrumentProfile,
    normalize_instrument_profile,
)
from ...models.score import (
    DEFAULT_TEMPO,
    Beam,
    BeamStatus,
    Beat,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
    TupletSpan,
)
from ...utils.safe_xml import safe_xml_fromstring
from ..endings import normalize_ending_number
from ..constants import (
    DYNAMICS,
    FIFTHS_TO_KEY,
    KEY_TO_TONIC,
    MICROTONAL_TOKEN_TO_ALTER,
    MUSICXML_ACCIDENTAL_TO_TOKEN,
    MUSICXML_METRONOME_UNIT_TO_SYMBOL,
    STEP_TO_SEMITONE,
)
from ..jianpu_tokens import is_notatable_duration
from ..performance_marks import canonical_mark_id, normalize_event_marks
from ..pitch_spelling import written_pitch_to_jianpu
from ..xml_utils import (
    _local_name,
    _namespace,
    _q,
    _read_musicxml,
    _text,
)

# 插入的音符来自未识别字形，其 MusicXML id 形如 ``st__n-s1-g7``，
# 因此 inter 段允许 i（Audiveris Inter）和 g（Glyph）两种来源。
_PROVENANCE_PART_RE = re.compile(
    r"(?:^|__)(?P<role>[a-z]+)\d*-s(?P<sheet>\d+)-(?P<kind>[ig])(?P<inter>\d+)"
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _InferredTupletNote:
    duration: Fraction
    group_id: str
    index: int
    count: int = 6
    normal_count: int = 4


def musicxml_path_to_scores(
    path: Path,
    target_key: str = "C",
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> list[JianpuScore]:
    return musicxml_to_scores(
        _read_musicxml(path),
        target_key,
        title,
        instrument_profile,
    )


def read_musicxml_text(path: Path) -> str:
    return _read_musicxml(path)


def musicxml_to_scores(
    xml_text: str,
    target_key: str = "C",
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> list[JianpuScore]:
    if target_key != "auto" and target_key not in KEY_TO_TONIC:
        raise ValueError(f"不支持的简谱调：{target_key}")

    root = safe_xml_fromstring(
        xml_text,
        source="MusicXML",
        allow_musicxml_doctype=True,
    )
    ns = _namespace(root.tag)
    xml_parts = root.findall(_q(ns, "part"))
    if not xml_parts:
        resolved = "C" if target_key == "auto" else target_key
        return [JianpuScore(title=title, target_key=resolved)]

    extracted_title = title or _extract_title(root, ns)
    profile = (
        normalize_instrument_profile(instrument_profile)
        if instrument_profile
        else _extract_instrument_profile(root, ns)
    )
    part_names = _extract_part_names(root, ns)

    raw_scores: list[JianpuScore] = []
    lyric_positions = _extract_lyric_positions(root, ns)
    for part_index, part_element in enumerate(xml_parts, start=1):
        part_target_key = target_key
        if target_key == "auto":
            source_key = _extract_first_key(part_element, ns)
            part_target_key = source_key or "C"
        part_id = part_element.get("id", "")
        part_name = part_names.get(part_id, "")
        score = _parse_single_part(
            part_element,
            ns,
            part_target_key,
            extracted_title,
            profile,
            follow_modulation=target_key == "auto",
        )
        matched_position_blocks: dict[int, set[int]] = {}
        for item in lyric_positions:
            if item.get("part") != part_index:
                continue
            measure_index = int(item.get("measure", 0)) - 1
            if not 0 <= measure_index < len(score.measures):
                continue
            start_value = item.get("start")
            if not isinstance(start_value, list) or len(start_value) != 2:
                continue
            start = Fraction(int(start_value[0]), int(start_value[1]))
            duration_value = item.get("duration")
            duration = (
                Fraction(int(duration_value[0]), int(duration_value[1]))
                if isinstance(duration_value, list) and len(duration_value) == 2
                else None
            )
            text = str(item.get("text", ""))
            verse = int(item.get("verse", 1))
            matched_for_measure = matched_position_blocks.setdefault(
                measure_index, set()
            )
            block_index = next(
                (
                    index
                    for index, block in enumerate(
                        score.measures[measure_index].text_blocks
                    )
                    if index not in matched_for_measure
                    and block.role == "lyric"
                    and block.text == text
                    and (block.lyric_verse or 1) == verse
                ),
                None,
            )
            block = (
                score.measures[measure_index].text_blocks[block_index]
                if block_index is not None
                else None
            )
            if block is not None:
                matched_for_measure.add(block_index)
                block.start = start
                block.duration = duration
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


def _extract_lyric_positions(root: ET.Element, ns: str) -> list[dict[str, object]]:
    for field in root.findall(f".//{_q(ns, 'miscellaneous-field')}"):
        if field.get("name") != "score-trans-lyric-positions":
            continue
        try:
            payload = json.loads(_text(field) or "[]")
        except json.JSONDecodeError:
            return []
        return (
            [item for item in payload if isinstance(item, dict)]
            if isinstance(payload, list)
            else []
        )
    return []


def musicxml_to_score(
    xml_text: str,
    target_key: str = "C",
    title: str | None = None,
    instrument_profile: InstrumentProfile | None = None,
) -> JianpuScore:
    scores = musicxml_to_scores(
        xml_text,
        target_key=target_key,
        title=title,
        instrument_profile=instrument_profile,
    )
    return scores[0] if scores else JianpuScore(title=title, target_key=target_key)


def _extract_first_key(part: ET.Element, ns: str) -> str | None:
    for xml_measure in part.findall(_q(ns, "measure")):
        attrs = xml_measure.find(_q(ns, "attributes"))
        if attrs is None:
            continue
        fifths = _text(attrs.find(f"{_q(ns, 'key')}/{_q(ns, 'fifths')}"))
        if fifths is not None:
            return FIFTHS_TO_KEY.get(int(fifths), "C")
    return None


def _parse_single_part(
    part: ET.Element,
    ns: str,
    target_key: str,
    extracted_title: str,
    instrument_profile: InstrumentProfile,
    *,
    follow_modulation: bool = False,
) -> JianpuScore:
    score = JianpuScore(
        title=extracted_title,
        target_key=target_key,
        instrument_profile=instrument_profile,
    )
    if extracted_title:
        score.text_blocks.append(TextBlock(text=extracted_title, role="title"))
    current_key = target_key
    current_beats = 4
    current_beat_type = 4
    divisions = 1
    initialized_score_time = False
    current_tempo = DEFAULT_TEMPO
    active_tuplets: list[tuple[str, str]] = []

    for index, xml_measure in enumerate(part.findall(_q(ns, "measure")), start=1):
        measure_tempo = _extract_measure_tempo(xml_measure, ns)
        if measure_tempo is not None:
            current_tempo = measure_tempo
        if index == 1 and measure_tempo is not None:
            score.tempo = measure_tempo
        attrs = xml_measure.find(_q(ns, "attributes"))
        if attrs is not None:
            divisions = int(_text(attrs.find(_q(ns, "divisions"))) or divisions)
            fifths = _text(attrs.find(f"{_q(ns, 'key')}/{_q(ns, 'fifths')}"))
            if fifths is not None:
                next_key = FIFTHS_TO_KEY.get(int(fifths), "C")
                if index > 1 and next_key != current_key:
                    if follow_modulation:
                        logger.info(
                            "小节 %s 跟随曲中转调：%s -> %s",
                            xml_measure.get("number", str(index)),
                            current_key,
                            next_key,
                        )
                    else:
                        logger.warning(
                            "小节 %s 检测到中途调号变化：%s -> %s；目标简谱调保持 %s",
                            xml_measure.get("number", str(index)),
                            current_key,
                            next_key,
                            target_key,
                        )
                current_key = next_key
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
            # 读取谱号（首小节生效，用于回写 MusicXML 时还原）
            if index == 1:
                for clef_el in attrs.findall(_q(ns, "clef")):
                    number = clef_el.get("number") or "1"
                    sign = _text(clef_el.find(_q(ns, "sign")))
                    line_text = _text(clef_el.find(_q(ns, "line")))
                    line = int(line_text) if line_text else None
                    if sign:
                        score.clefs_by_staff[number] = (sign, line)
                        if score.clef_sign is None or number == "1":
                            score.clef_sign = sign
                            score.clef_line = line
            score.source_key = current_key

        display_number = _display_measure_number(xml_measure, index)
        effective_target = current_key if follow_modulation else target_key
        measure = Measure(
            source_number=xml_measure.get("number", str(index)),
            display_measure_number=display_number,
            duration=Fraction(current_beats * 4, current_beat_type),
            beats_per_measure=current_beats,
            beat_type=current_beat_type,
            tempo=current_tempo,
            source_key=current_key,
            target_key=effective_target,
        )
        measure.text_blocks.append(
            TextBlock(
                text=str(display_number),
                role="measure_number",
                measure_number=display_number,
            )
        )
        _read_measure_structure(xml_measure, ns, measure)
        _read_measure_events(
            xml_measure,
            ns,
            divisions,
            effective_target,
            measure,
            active_tuplets,
        )
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
            tempo=score.tempo,
            instrument_profile=score.instrument_profile,
            part_name=score.part_name,
        )
        # 按 staff 分配谱号；无对应记录时回退到 part 级谱号
        staff_clef = score.clefs_by_staff.get(staff)
        if staff_clef:
            staff_score.clef_sign, staff_score.clef_line = staff_clef
        else:
            staff_score.clef_sign = score.clef_sign
            staff_score.clef_line = score.clef_line
        staff_score.clefs_by_staff = dict(score.clefs_by_staff)
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
                tempo=measure.tempo,
                source_key=measure.source_key,
                target_key=measure.target_key,
                repeat_start=measure.repeat_start,
                repeat_end=measure.repeat_end,
                repeat_count=measure.repeat_count,
                ending_start=measure.ending_start,
                ending_stop=measure.ending_stop,
                ending_discontinue=measure.ending_discontinue,
                new_page=measure.new_page,
                new_system=measure.new_system,
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
                staff_measure,
                staff_measure.beats_per_measure,
                staff_measure.beat_type,
                pad_empty=True,
            )
            staff_score.measures.append(staff_measure)
        staff_score.part_staff = staff
        results.append(staff_score)
    return results if results else [score]


def _extract_title(root: ET.Element, ns: str) -> str | None:
    work_title = root.find(f"{_q(ns, 'work')}/{_q(ns, 'work-title')}")
    movement_title = root.find(_q(ns, "movement-title"))
    return _text(work_title) or _text(movement_title)


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


def _extract_measure_tempo(measure: ET.Element, ns: str) -> int | None:
    for sound in measure.findall(f".//{_q(ns, 'sound')}"):
        value = sound.get("tempo")
        if value:
            try:
                tempo = int(float(value))
            except ValueError:
                continue
            if 20 <= tempo <= 300:
                return tempo
    for metronome in measure.findall(f".//{_q(ns, 'metronome')}"):
        value = _text(metronome.find(_q(ns, "per-minute")))
        if value:
            try:
                tempo = int(float(value))
            except ValueError:
                continue
            if 20 <= tempo <= 300:
                return tempo
    return None


def _display_measure_number(measure: ET.Element, fallback: int) -> str | int:
    raw = measure.get("number")
    if raw is None or raw.strip() == "":
        return fallback
    try:
        return int(raw)
    except ValueError:
        return raw


def _read_measure_structure(
    xml_measure: ET.Element,
    ns: str,
    measure: Measure,
) -> None:
    print_element = xml_measure.find(_q(ns, "print"))
    if print_element is not None:
        measure.new_page = _is_yes(print_element.get("new-page"))
        measure.new_system = _is_yes(print_element.get("new-system"))

    for barline in xml_measure.findall(_q(ns, "barline")):
        repeat = barline.find(_q(ns, "repeat"))
        if repeat is not None:
            direction = (repeat.get("direction") or "").strip().lower()
            if direction == "forward":
                measure.repeat_start = True
            elif direction == "backward":
                measure.repeat_end = True
                times = repeat.get("times")
                if times:
                    try:
                        parsed_times = int(times)
                    except ValueError:
                        pass
                    else:
                        if parsed_times > 0:
                            measure.repeat_count = parsed_times

        ending = barline.find(_q(ns, "ending"))
        if ending is None:
            continue
        number = (ending.get("number") or "").strip()
        ending_type = (ending.get("type") or "").strip().lower()
        try:
            number = normalize_ending_number(number)
        except ValueError:
            # 无效编号（空值、非正整数等）：丢弃该房子标记，不阻断整体转换。
            continue
        if ending_type == "start":
            measure.ending_start = number
        elif ending_type == "stop":
            measure.ending_stop = number
        elif ending_type == "discontinue":
            measure.ending_discontinue = number


def _is_yes(value: str | None) -> bool:
    return (value or "").strip().lower() in {"yes", "true", "1"}


def _read_measure_events(
    xml_measure: ET.Element,
    ns: str,
    divisions: int,
    target_key: str,
    measure: Measure,
    active_tuplets: list[tuple[str, str]],
) -> None:
    last_event: Event | None = None
    cursor = Fraction(0, 1)
    pending_dynamics: list[tuple[Fraction, str]] = []
    parsed_notes: list[tuple[ET.Element, Event]] = []
    seen_note_ids: set[str] = set()
    inferred_tuplets = _infer_unmarked_sextuplets(
        xml_measure,
        ns,
        divisions,
        measure.beats_per_measure,
        measure.beat_type,
    )
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
        note_id = (note.get("id") or "").strip()
        if note_id:
            if note_id in seen_note_ids:
                continue
            seen_note_ids.add(note_id)
        inferred_tuplet = inferred_tuplets.get(note)
        duration = (
            inferred_tuplet.duration
            if inferred_tuplet is not None
            else Fraction(
                int(_text(note.find(_q(ns, "duration"))) or 0),
                divisions,
            )
        )
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
                for beam in _read_beams(note, ns):
                    if not any(
                        existing.number == beam.number
                        and existing.status == beam.status
                        for existing in last_event.beams
                    ):
                        last_event.beams.append(beam)
                notations = note.find(_q(ns, "notations"))
                if notations is not None:
                    last_event.slur_start = last_event.slur_start or any(
                        slur.get("type") == "start"
                        for slur in notations.findall(_q(ns, "slur"))
                    )
                    last_event.slur_stop = last_event.slur_stop or any(
                        slur.get("type") == "stop"
                        for slur in notations.findall(_q(ns, "slur"))
                    )
                _merge_event_provenance(last_event, provenance)
            continue

        rest_element = note.find(_q(ns, "rest"))
        if rest_element is not None:
            measure_rest = _is_yes(rest_element.get("measure"))
            if measure_rest:
                duration = measure.duration
            event = Event(
                kind="rest",
                duration=duration,
                measure_rest=measure_rest,
            )
            if note.get("print-object") == "no":
                event.hidden = True
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
        event.dotted = (
            0 if inferred_tuplet is not None else len(note.findall(_q(ns, "dot")))
        )
        event.tie_start = any(
            tie.get("type") == "start" for tie in note.findall(_q(ns, "tie"))
        )
        event.tie_stop = any(
            tie.get("type") == "stop" for tie in note.findall(_q(ns, "tie"))
        )
        event.beams = _read_beams(note, ns)
        event.voice = _text(note.find(_q(ns, "voice")))
        event.staff = _text(note.find(_q(ns, "staff")))
        event.start = cursor
        notations = note.find(_q(ns, "notations"))
        _apply_tuplet_notations(
            event,
            notations,
            ns,
            measure.source_number,
            cursor,
            active_tuplets,
        )
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
            normalize_event_marks(event)
        time_modification = note.find(_q(ns, "time-modification"))
        if time_modification is not None:
            actual_notes = _text(time_modification.find(_q(ns, "actual-notes")))
            if actual_notes and actual_notes.isdigit():
                event.tuplet_count = int(actual_notes)
            normal_notes = _text(time_modification.find(_q(ns, "normal-notes")))
            if normal_notes and normal_notes.isdigit():
                event.tuplet_normal_count = int(normal_notes)
            notated_duration = _musicxml_note_type_duration(note, ns)
            if (
                event.tuplet_count
                and event.tuplet_normal_count
                and notated_duration is not None
                and event.duration == notated_duration
            ):
                duration = notated_duration * Fraction(
                    event.tuplet_normal_count,
                    event.tuplet_count,
                )
                event.duration = duration
        if inferred_tuplet is not None:
            event.tuplet_id = inferred_tuplet.group_id
            event.tuplet_count = inferred_tuplet.count
            event.tuplet_normal_count = inferred_tuplet.normal_count
            event.tuplet_index = inferred_tuplet.index
            event.tuplet_start = inferred_tuplet.index == 0
            event.tuplet_stop = inferred_tuplet.index == inferred_tuplet.count - 1
            event.tuplet_spans = [
                TupletSpan(
                    id=inferred_tuplet.group_id,
                    start=event.tuplet_start,
                    stop=event.tuplet_stop,
                )
            ]
        if (
            event.tuplet_count
            and event.tuplet_normal_count
            and event.tuplet_count != event.tuplet_normal_count
            and event.duration > 0
        ):
            notated_if_sounded = event.duration * Fraction(
                event.tuplet_count, event.tuplet_normal_count
            )
            if not is_notatable_duration(notated_if_sounded) and is_notatable_duration(
                event.duration
            ):
                duration = event.duration * Fraction(
                    event.tuplet_normal_count, event.tuplet_count
                )
                event.duration = duration
        dynamic = _pending_dynamic_for_event(pending_dynamics, cursor)
        if dynamic is not None:
            pending_dynamics = [
                pending for pending in pending_dynamics if pending[0] > cursor
            ]
            if event.dynamic is None:
                event.dynamic = dynamic
        for lyric_index, lyric in enumerate(note.findall(_q(ns, "lyric")), start=1):
            lyric_text = "".join(
                _text(child) for child in lyric.findall(_q(ns, "text"))
            ).strip()
            if not lyric_text:
                continue
            if event.kind != "note":
                continue
            number = lyric.get("number")
            try:
                verse = int(number) if number else lyric_index
            except ValueError:
                verse = lyric_index
            event.lyrics[verse] = lyric_text
            if verse == 1:
                event.lyric = lyric_text
            measure.text_blocks.append(
                TextBlock(
                    text=lyric_text,
                    role="lyric",
                    measure_number=measure.display_measure_number,
                    start=cursor,
                    placement="below",
                    lyric_verse=verse,
                    duration=duration,
                )
            )
        measure.events.append(event)
        parsed_notes.append((note, event))
        last_event = event
        cursor += duration
    _recover_unmarked_time_modified_tuplets(
        parsed_notes,
        ns,
        measure.source_number,
    )


def _recover_unmarked_time_modified_tuplets(
    parsed_notes: list[tuple[ET.Element, Event]],
    ns: str,
    measure_number: str,
) -> None:
    notes_by_voice_staff: dict[
        tuple[str, str],
        list[tuple[ET.Element, Event]],
    ] = {}
    for note, event in parsed_notes:
        key = (event.voice or "1", event.staff or "")
        notes_by_voice_staff.setdefault(key, []).append((note, event))

    group_counter = 0
    for (voice, staff), note_events in notes_by_voice_staff.items():
        beam_group: list[tuple[ET.Element, Event]] = []
        for note_event in note_events:
            beam_status = _beam_status(note_event[0], ns, "1")
            if beam_status == "begin":
                beam_group = [note_event]
                continue
            if beam_status == "continue" and beam_group:
                beam_group.append(note_event)
                continue
            if beam_status == "end" and beam_group:
                beam_group.append(note_event)
                if _recover_time_modified_group(
                    beam_group,
                    measure_number,
                    voice,
                    staff,
                    group_counter,
                ):
                    group_counter += 1
                beam_group = []
                continue
            beam_group = []

        pending: list[tuple[ET.Element, Event]] = []
        pending_ratio: tuple[int, int] | None = None
        for note_event in note_events:
            event = note_event[1]
            ratio = _event_tuplet_ratio(event)
            if event.tuplet_id is not None or ratio is None:
                group_counter = _recover_pending_time_modified_groups(
                    pending,
                    pending_ratio,
                    measure_number,
                    voice,
                    staff,
                    group_counter,
                )
                pending = []
                pending_ratio = None
                continue
            if pending_ratio is not None and ratio != pending_ratio:
                group_counter = _recover_pending_time_modified_groups(
                    pending,
                    pending_ratio,
                    measure_number,
                    voice,
                    staff,
                    group_counter,
                )
                pending = []
            pending.append(note_event)
            pending_ratio = ratio
        group_counter = _recover_pending_time_modified_groups(
            pending,
            pending_ratio,
            measure_number,
            voice,
            staff,
            group_counter,
        )


def _recover_pending_time_modified_groups(
    pending: list[tuple[ET.Element, Event]],
    ratio: tuple[int, int] | None,
    measure_number: str,
    voice: str,
    staff: str,
    group_counter: int,
) -> int:
    if not pending or ratio is None:
        return group_counter
    actual_count, _normal_count = ratio
    cursor = 0
    while cursor < len(pending):
        group = pending[cursor : cursor + actual_count]
        if _recover_time_modified_group(
            group,
            measure_number,
            voice,
            staff,
            group_counter,
        ):
            group_counter += 1
        cursor += len(group)
    return group_counter


def _recover_time_modified_group(
    note_events: list[tuple[ET.Element, Event]],
    measure_number: str,
    voice: str,
    staff: str,
    group_counter: int,
) -> bool:
    if not note_events:
        return False
    events = [event for _note, event in note_events]
    ratio = _event_tuplet_ratio(events[0])
    if ratio is None or any(
        event.tuplet_id is not None or _event_tuplet_ratio(event) != ratio
        for event in events
    ):
        return False
    actual_count, normal_count = ratio
    group_id = (
        f"{measure_number}:recovered:{voice}:{staff or 'default'}:{group_counter}"
    )
    for index, event in enumerate(events):
        event.tuplet_id = group_id
        event.tuplet_count = actual_count
        event.tuplet_normal_count = normal_count
        event.tuplet_index = index
        event.tuplet_start = index == 0
        event.tuplet_stop = index == len(events) - 1
        event.tuplet_spans = [
            TupletSpan(
                id=group_id,
                start=event.tuplet_start,
                stop=event.tuplet_stop,
            )
        ]
    return True


def _event_tuplet_ratio(event: Event) -> tuple[int, int] | None:
    actual_count = event.tuplet_count
    normal_count = event.tuplet_normal_count
    if (
        actual_count is None
        or normal_count is None
        or actual_count <= 0
        or normal_count <= 0
        or actual_count == normal_count
    ):
        return None
    return actual_count, normal_count


def _infer_unmarked_sextuplets(
    xml_measure: ET.Element,
    ns: str,
    divisions: int,
    beats: int,
    beat_type: int,
) -> dict[ET.Element, _InferredTupletNote]:
    if divisions <= 0 or beats <= 0 or beat_type != 4:
        return {}

    notes_by_voice: dict[str, list[ET.Element]] = {}
    for note in xml_measure.findall(_q(ns, "note")):
        if note.find(_q(ns, "chord")) is not None:
            continue
        voice = _text(note.find(_q(ns, "voice"))) or "1"
        notes_by_voice.setdefault(voice, []).append(note)

    inferred: dict[ET.Element, _InferredTupletNote] = {}
    for voice, notes in notes_by_voice.items():
        if any(
            note.find(_q(ns, "time-modification")) is not None
            or note.find(f"{_q(ns, 'notations')}/{_q(ns, 'tuplet')}") is not None
            for note in notes
        ):
            continue
        groups = _complete_six_note_beam_groups(notes, ns)
        if groups is None or len(groups) != beats:
            continue

        notated_duration = Fraction(1, 4)
        allowed_raw_durations = {
            notated_duration,
            notated_duration * Fraction(3, 2),
        }
        raw_durations = [
            Fraction(
                int(_text(note.find(_q(ns, "duration"))) or 0),
                divisions,
            )
            for group in groups
            for note in group
        ]
        expected_duration = Fraction(beats, 1)
        if (
            any(duration not in allowed_raw_durations for duration in raw_durations)
            or sum(raw_durations, start=Fraction(0, 1)) <= expected_duration
        ):
            continue

        actual_duration = notated_duration * Fraction(4, 6)
        if actual_duration * 6 * len(groups) != expected_duration:
            continue
        measure_number = xml_measure.get("number", "")
        for group_index, group in enumerate(groups):
            group_id = f"{measure_number}:implicit-6:{voice}:{group_index}"
            for event_index, note in enumerate(group):
                inferred[note] = _InferredTupletNote(
                    duration=actual_duration,
                    group_id=group_id,
                    index=event_index,
                )
    return inferred


def _complete_six_note_beam_groups(
    notes: list[ET.Element],
    ns: str,
) -> list[list[ET.Element]] | None:
    groups: list[list[ET.Element]] = []
    current: list[ET.Element] = []
    for note in notes:
        if _text(note.find(_q(ns, "type"))) != "16th":
            return None
        first_beam = _beam_status(note, ns, "1")
        second_beam = _beam_status(note, ns, "2")
        if first_beam != second_beam:
            return None
        if first_beam == "begin":
            if current:
                return None
            current = [note]
        elif first_beam == "continue" and current:
            current.append(note)
        elif first_beam == "end" and current:
            current.append(note)
            if len(current) != 6:
                return None
            groups.append(current)
            current = []
        else:
            return None
    return groups if groups and not current else None


def _beam_status(note: ET.Element, ns: str, number: str) -> str | None:
    for beam in note.findall(_q(ns, "beam")):
        if (beam.get("number") or "1") == number:
            return (_text(beam) or "").casefold()
    return None


def _read_beams(note: ET.Element, ns: str) -> list[Beam]:
    beams: list[Beam] = []
    for beam in note.findall(_q(ns, "beam")):
        status = (_text(beam) or "").casefold()
        if status not in {
            "begin",
            "continue",
            "end",
            "forward-hook",
            "backward-hook",
        }:
            continue
        beams.append(
            Beam(
                number=beam.get("number") or "1",
                status=cast(BeamStatus, status),
            )
        )
    return beams


def _note_provenance(note: ET.Element) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    xml_id = note.get("id") or ""
    for match in _PROVENANCE_PART_RE.finditer(xml_id):
        role = _source_role(match.group("role"))
        source_id = (
            f"s{match.group('sheet')}:{match.group('kind')}{match.group('inter')}"
        )
        result.setdefault(role, []).append(source_id)
    return result


def _source_role(code: str) -> str:
    return {
        "n": "note",
        "a": "accidental",
        "ad": "augmentation_dot",
        "ss": "slur_start",
        "se": "slur_stop",
        "ts": "tie_start",
        "te": "tie_stop",
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
    notations: ET.Element | None,
    ns: str,
    measure_number: str,
    cursor: Fraction,
    active_tuplets: list[tuple[str, str]],
) -> None:
    event.tuplet_spans = [
        TupletSpan(id=group_id, number=number) for number, group_id in active_tuplets
    ]
    if notations is None:
        _sync_primary_tuplet(event)
        return

    for tuplet in notations.findall(_q(ns, "tuplet")):
        number = tuplet.get("number") or "1"
        kind = tuplet.get("type")
        if kind == "start":
            group_id = f"{measure_number}:{number}:{cursor}:{len(active_tuplets)}"
            active_tuplets.append((number, group_id))
            event.tuplet_spans.append(
                TupletSpan(id=group_id, number=number, start=True)
            )
        if kind == "stop":
            active_index = next(
                (
                    index
                    for index in range(len(active_tuplets) - 1, -1, -1)
                    if active_tuplets[index][0] == number
                ),
                None,
            )
            if active_index is None:
                continue
            _active_number, group_id = active_tuplets[active_index]
            span = next(
                (item for item in event.tuplet_spans if item.id == group_id),
                None,
            )
            if span is None:
                span = TupletSpan(id=group_id, number=number)
                event.tuplet_spans.append(span)
            span.stop = True
            active_tuplets.pop(active_index)
    _sync_primary_tuplet(event)


def _sync_primary_tuplet(event: Event) -> None:
    if not event.tuplet_spans:
        return
    # 优先取带 start 的 span（真正的连音起点），其次取带 stop 的 span（终点），
    # 最后兜底取最后一个。原实现直接取 spans[0]，但 active_tuplets 跨小节残留的
    # 未闭合 tuplet span 会混入，导致 spans[0] 是残留项（start/stop 均为 False），
    # 从而丢失真正的 tuplet start/stop 标记；对非边界事件（无 start/stop），
    # 应取最后活跃的组（active_tuplets 按 start 顺序追加）而不是第一个残留项。
    primary = next((sp for sp in event.tuplet_spans if sp.start), None)
    if primary is None:
        primary = next((sp for sp in event.tuplet_spans if sp.stop), None)
    if primary is None:
        primary = event.tuplet_spans[-1]
    event.tuplet_id = primary.id
    event.tuplet_start = primary.start
    event.tuplet_stop = primary.stop


def _normalize_measure(
    measure: Measure,
    beats: int,
    beat_type: int,
    *,
    pad_empty: bool = False,
) -> None:
    target = Fraction(beats * 4, beat_type)
    actual = measure.span_duration
    if actual < target:
        if pad_empty and actual == 0:
            measure.events.append(
                Event(
                    kind="rest",
                    duration=target - actual,
                    start=actual,
                    generated=True,
                )
            )
        else:
            measure.validation_errors.append(f"小节少拍：实际 {actual}，目标 {target}")
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
    alter = Fraction(_text(pitch.find(_q(ns, "alter"))) or "0")
    octave = int(_text(pitch.find(_q(ns, "octave"))) or "4")
    accidental_text = _accidental_token(_text(note.find(_q(ns, "accidental"))))
    midi = (octave + 1) * 12 + STEP_TO_SEMITONE[step] + alter
    degree, accidental, octave_shift = written_pitch_to_jianpu(
        step, alter, octave, target_key
    )
    return JianpuPitch(
        degree=degree,
        octave=octave_shift,
        accidental=accidental,
        midi=midi,
        step=step,
        alter=alter,
        accidental_text=_matching_accidental_text(
            accidental_text,
            alter,
            accidental,
        ),
    )


def _duration_from_child(element: ET.Element, ns: str, divisions: int) -> Fraction:
    return Fraction(int(_text(element.find(_q(ns, "duration"))) or 0), divisions)


def _musicxml_note_type_duration(note: ET.Element, ns: str) -> Fraction | None:
    note_type = (_text(note.find(_q(ns, "type"))) or "").casefold()
    base = {
        "maxima": Fraction(32, 1),
        "long": Fraction(16, 1),
        "breve": Fraction(8, 1),
        "whole": Fraction(4, 1),
        "half": Fraction(2, 1),
        "quarter": Fraction(1, 1),
        "eighth": Fraction(1, 2),
        "16th": Fraction(1, 4),
        "32nd": Fraction(1, 8),
        "64th": Fraction(1, 16),
        "128th": Fraction(1, 32),
        "256th": Fraction(1, 64),
    }.get(note_type)
    if base is None:
        return None
    dot_count = len(note.findall(_q(ns, "dot")))
    return base * (2 - Fraction(1, 2**dot_count)) if dot_count else base


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
                        "words",
                    )
                )

        for rehearsal in direction_type.findall(_q(ns, "rehearsal")):
            text = _text(rehearsal)
            if text:
                blocks.append(
                    _measure_text_block(
                        text,
                        measure_number,
                        start,
                        placement,
                        staff,
                        "rehearsal",
                    )
                )

        dynamics = direction_type.find(_q(ns, "dynamics"))
        dynamic = _dynamic_text(dynamics, ns)
        if dynamic:
            blocks.append(
                _measure_text_block(
                    dynamic,
                    measure_number,
                    start,
                    (dynamics.get("placement") if dynamics is not None else None)
                    or placement,
                    staff,
                    "dynamics",
                )
            )

        metronome = direction_type.find(_q(ns, "metronome"))
        metronome_text = _metronome_text(metronome, ns)
        if metronome_text:
            blocks.append(
                _measure_text_block(
                    metronome_text,
                    measure_number,
                    start,
                    placement,
                    staff,
                    "metronome",
                )
            )

        for wedge in direction_type.findall(_q(ns, "wedge")):
            wedge_text = _wedge_text(wedge.get("type")) or _structural_direction_text(
                "wedge", wedge.get("type")
            )
            blocks.append(
                _measure_text_block(
                    wedge_text,
                    measure_number,
                    start,
                    placement,
                    staff,
                    "wedge",
                    dict(wedge.attrib),
                )
            )

        for pedal in direction_type.findall(_q(ns, "pedal")):
            pedal_text = _pedal_text(pedal.get("type")) or _structural_direction_text(
                "pedal", pedal.get("type")
            )
            blocks.append(
                _measure_text_block(
                    pedal_text,
                    measure_number,
                    start,
                    placement,
                    staff,
                    "pedal",
                    dict(pedal.attrib),
                )
            )

        for octave_shift in direction_type.findall(_q(ns, "octave-shift")):
            shift_text = _octave_shift_text(
                octave_shift.get("type"), octave_shift.get("size")
            )
            shift_text = shift_text or _structural_direction_text(
                "octave-shift", octave_shift.get("type")
            )
            blocks.append(
                _measure_text_block(
                    shift_text,
                    measure_number,
                    start,
                    placement,
                    staff,
                    "octave-shift",
                    dict(octave_shift.attrib),
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
                    _measure_text_block(
                        text, measure_number, start, placement, staff, name
                    )
                )
    return blocks


def _measure_text_block(
    text: str,
    measure_number: str | int,
    start: Fraction,
    placement: str | None,
    staff: str | None,
    direction_kind: str | None = None,
    direction_attributes: dict[str, str] | None = None,
) -> TextBlock:
    return TextBlock(
        text=text,
        role="expression",
        measure_number=measure_number,
        start=start,
        placement=placement,
        staff=staff,
        direction_kind=direction_kind,
        direction_attributes=direction_attributes or {},
    )


def _pending_dynamic_for_event(
    pending_dynamics: list[tuple[Fraction, str]], cursor: Fraction
) -> str | None:
    eligible = [
        (start, index, dynamic)
        for index, (start, dynamic) in enumerate(pending_dynamics)
        if start <= cursor
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item[0], item[1]))[2]


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
        elif text and (
            name in {"string", "fret"}
            or name in {"other-technical", "other-ornament", "other-articulation"}
        ):
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
        symbol = MUSICXML_METRONOME_UNIT_TO_SYMBOL.get(unit, unit)
        dots = "." * len(metronome.findall(_q(ns, "beat-unit-dot")))
        return f"{symbol}{dots}={per_minute}"
    return _text(metronome)


def _wedge_text(kind: str | None) -> str | None:
    if kind == "crescendo":
        return "cresc."
    if kind == "diminuendo":
        return "dim."
    if kind == "stop":
        return "wedge stop"
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


def _structural_direction_text(name: str, kind: str | None) -> str:
    return f"{name} {kind}" if kind else name


def _direction_symbol_text(name: str) -> str | None:
    if name in {"segno", "coda", "dacapo", "dalsegno", "tocoda", "fine"}:
        return name
    return None


def _is_dynamic_name(text: str) -> bool:
    return text in DYNAMICS


def _accidental_token(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-").replace(" ", "-")
    return MUSICXML_ACCIDENTAL_TO_TOKEN.get(normalized)


def _matching_accidental_text(
    value: str | None,
    written_alter: Fraction,
    accidental: Fraction,
) -> str | None:
    if value is None:
        return None
    token_value = {
        "bb": Fraction(-2, 1),
        "b": Fraction(-1, 1),
        "n": Fraction(0, 1),
        "#": Fraction(1, 1),
        "x": Fraction(2, 1),
        **MICROTONAL_TOKEN_TO_ALTER,
    }.get(value)
    if token_value != written_alter:
        return None
    if token_value == accidental:
        return value
    if value == "n":
        return value
    return {
        Fraction(-2, 1): "bb",
        Fraction(-3, 2): "tqf",
        Fraction(-1, 1): "b",
        Fraction(-1, 2): "qf",
        Fraction(0, 1): "",
        Fraction(1, 2): "qs",
        Fraction(1, 1): "#",
        Fraction(3, 2): "tqs",
        Fraction(2, 1): "x",
    }.get(accidental)
