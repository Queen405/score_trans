from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import re

from ..accidentals import pitch_to_token
from ..jianpu_tokens import duration_affixes
from ..performance_marks import event_mark_ids, mark_token
from ...models.common.types import AccidentalMode, normalize_instrument_profile
from ...models.score import Event, JianpuPitch, JianpuScore, Measure
from ...models.provenance.entities import JianpuDocument
from ...models.provenance.schemas import TextAnchor

_CONTINUOUS_SLIDE_TOKEN = mark_token("continuous-slide") or "lh"


def score_to_jianpu_text(
    score: JianpuScore,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return score_to_jianpu_document(score, accidental_mode=accidental_mode).text


def score_to_jianpu_document(
    score: JianpuScore,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> JianpuDocument:
    text = _score_to_jianpu_text(score, accidental_mode=accidental_mode)
    return JianpuDocument(
        text=text,
        anchors=_text_anchors(score, text, accidental_mode=accidental_mode),
        text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def scores_to_jianpu_text(
    scores: list[JianpuScore],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return scores_to_jianpu_document(scores, accidental_mode=accidental_mode).text


def scores_to_jianpu_document(
    scores: list[JianpuScore],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> JianpuDocument:
    if len(scores) <= 1:
        score = scores[0] if scores else JianpuScore()
        return score_to_jianpu_document(score, accidental_mode=accidental_mode)

    part_anchors: list[list[TextAnchor]] = []
    part_offsets: list[int] = []

    full_text = ""
    for index, score in enumerate(scores):
        part_text = _score_to_jianpu_text(score, accidental_mode=accidental_mode)
        part_anchors.append(
            _text_anchors_raw(score, part_text, accidental_mode=accidental_mode)
        )
        encoded_name = json.dumps(score.part_name, ensure_ascii=False)
        marker = f"// @part {index + 1} name={encoded_name}"
        full_text += marker + "\n"
        part_offsets.append(len(full_text))
        full_text += part_text
        if index < len(scores) - 1:
            full_text += "\n"
    all_anchors: list[TextAnchor] = []
    for index, anchors in enumerate(part_anchors):
        offset = part_offsets[index]
        for anchor in anchors:
            anchor.start_utf16 += offset
            anchor.end_utf16 += offset
            all_anchors.append(anchor)

    for anchor in all_anchors:
        anchor.start_utf16 = _utf16_offset(full_text, anchor.start_utf16)
        anchor.end_utf16 = _utf16_offset(full_text, anchor.end_utf16)
    all_anchors.sort(key=lambda a: (a.start_utf16, a.end_utf16))

    return JianpuDocument(
        text=full_text,
        anchors=all_anchors,
        text_hash=hashlib.sha256(full_text.encode("utf-8")).hexdigest(),
    )


def _measure_lead_info(
    measure: Measure,
    current_key: str,
    current_beats: int,
    current_beat_type: int,
) -> tuple[list[str], str, str, int, int]:
    lead_tokens: list[str] = []
    if measure.target_key != current_key:
        lead_tokens.append(f"1={measure.target_key}")
        current_key = measure.target_key
    if (
        measure.beats_per_measure != current_beats
        or measure.beat_type != current_beat_type
    ):
        lead_tokens.append(f"{measure.beats_per_measure}/{measure.beat_type}")
        current_beats = measure.beats_per_measure
        current_beat_type = measure.beat_type
    prefix = "|: " if measure.repeat_start else ""
    return lead_tokens, prefix, current_key, current_beats, current_beat_type


def _lead_skip_length(lead_tokens: list[str], prefix: str) -> int:
    if not lead_tokens:
        return len(prefix)
    return len(prefix) + len(" ".join(lead_tokens)) + 1


def _score_to_jianpu_text(
    score: JianpuScore,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    first_measure = score.measures[0] if score.measures else None
    current_key = (
        getattr(first_measure, "target_key", score.target_key)
        if first_measure
        else score.target_key
    )
    current_beats = (
        getattr(first_measure, "beats_per_measure", score.beats)
        if first_measure
        else score.beats
    )
    current_beat_type = (
        getattr(first_measure, "beat_type", score.beat_type)
        if first_measure
        else score.beat_type
    )
    lines = [f"1={current_key}", f"{current_beats}/{current_beat_type}"]
    if score.tempo is not None:
        lines.insert(0, f"tempo={score.tempo}")
    instrument_profile = normalize_instrument_profile(score.instrument_profile)
    if instrument_profile != "general":
        lines.insert(0, f"instrument={instrument_profile}")
    if score.title and score.title != "简谱":
        lines.insert(0, f"title={score.title}")
    measures = []
    lyrics: list[str] = []
    for measure in score.measures:
        lead_tokens, prefix, current_key, current_beats, current_beat_type = (
            _measure_lead_info(measure, current_key, current_beats, current_beat_type)
        )
        events = measure.events
        tokens = []
        index = 0
        while index < len(events):
            event = events[index]
            if event.tuplet_start and event.tuplet_count:
                group = _collect_tuplet_events(events, index)
                tokens.append(_tuplet_to_token(group, accidental_mode=accidental_mode))
                for group_event in group:
                    if group_event.lyric:
                        lyrics.append(group_event.lyric)
                index += len(group)
                continue
            if event.dynamic:
                tokens.append(f"\\{event.dynamic}")
            articulations = list(
                event.articulations
                or ([event.articulation] if event.articulation else [])
            )
            for mark in event_mark_ids(
                articulations,
                list(event.ornaments),
                list(event.technical),
            ):
                token = _mark_token(mark)
                if token:
                    tokens.append(f"^{token}")
            if event.slide_stop:
                tokens.append(f"^{_CONTINUOUS_SLIDE_TOKEN}")
            tokens.append(_event_to_token(event, accidental_mode=accidental_mode))
            if event.lyric:
                lyrics.append(event.lyric)
            index += 1
        repeat_count = getattr(measure, "repeat_count", 1)
        repeat_suffix = f" *{repeat_count}" if repeat_count > 1 else ""
        suffix = " :|" if getattr(measure, "repeat_end", False) else ""
        body = " ".join([*lead_tokens, *tokens])
        measures.append(prefix + body + repeat_suffix + suffix)
    for m in measures:
        lines.append(m + " |")
    if lyrics:
        lines.append(f"L: {' '.join(lyrics)}")
    return "\n".join(lines)


def _text_anchors(
    score: JianpuScore,
    text: str,
    *,
    accidental_mode: AccidentalMode,
) -> list[TextAnchor]:
    anchors = _text_anchors_raw(score, text, accidental_mode=accidental_mode)
    for anchor in anchors:
        anchor.start_utf16 = _utf16_offset(text, anchor.start_utf16)
        anchor.end_utf16 = _utf16_offset(text, anchor.end_utf16)
    anchors.sort(key=lambda anchor: (anchor.start_utf16, anchor.end_utf16))
    return anchors


def _text_anchors_raw(
    score: JianpuScore,
    text: str,
    *,
    accidental_mode: AccidentalMode,
) -> list[TextAnchor]:
    if not score.measures:
        return []

    lines = text.splitlines(keepends=True)
    lyric_line_count = 1 if lines and lines[-1].lstrip().startswith("L:") else 0
    first_measure_line = len(lines) - len(score.measures) - lyric_line_count
    if first_measure_line < 0:
        return []

    anchors: list[TextAnchor] = []
    seen: set[tuple[str, int, int, str]] = set()
    line_offset = sum(len(line) for line in lines[:first_measure_line])
    first_measure = score.measures[0]
    current_key = first_measure.target_key
    current_beats = first_measure.beats_per_measure
    current_beat_type = first_measure.beat_type
    for measure_index, measure in enumerate(score.measures):
        line = lines[first_measure_line + measure_index].rstrip("\r\n")
        lead_tokens, prefix, current_key, current_beats, current_beat_type = (
            _measure_lead_info(measure, current_key, current_beats, current_beat_type)
        )
        event_cursor = _lead_skip_length(lead_tokens, prefix)
        events = measure.events
        index = 0
        while index < len(events):
            event = events[index]
            if event.tuplet_start and event.tuplet_count:
                group = _collect_tuplet_events(events, index)
                group_open = line.find("$", event_cursor)
                group_close = line.find("$", group_open + 1) if group_open >= 0 else -1
                for group_event in group:
                    token = _event_to_tuplet_body(
                        group_event, accidental_mode=accidental_mode
                    )
                    position = line.find(
                        token,
                        event_cursor,
                        group_close if group_close >= 0 else len(line),
                    )
                    if position < 0:
                        event_cursor = (
                            group_close + 1
                            if group_close >= 0
                            else _advance_past_text_tokens(line, event_cursor)
                        )
                        break
                    _append_event_anchors(
                        anchors,
                        seen,
                        group_event,
                        token,
                        line_offset + position,
                        line,
                        event_cursor,
                        position,
                        accidental_mode,
                    )
                    event_cursor = position + len(token)
                if group_close >= 0:
                    event_cursor = group_close + 1
                index += len(group)
                continue

            token = _event_to_token(event, accidental_mode=accidental_mode)
            position = line.find(token, event_cursor)
            if position < 0:
                event_cursor = _advance_past_text_tokens(
                    line,
                    event_cursor,
                    count=_rendered_event_token_count(event),
                )
                index += 1
                continue
            _append_event_anchors(
                anchors,
                seen,
                event,
                token,
                line_offset + position,
                line,
                event_cursor,
                position,
                accidental_mode,
            )
            event_cursor = position + len(token)
            index += 1
        line_offset += len(lines[first_measure_line + measure_index])
    return anchors


def _append_event_anchors(
    anchors: list[TextAnchor],
    seen: set[tuple[str, int, int, str]],
    event: Event,
    token: str,
    absolute_start: int,
    line: str,
    segment_start: int,
    token_start: int,
    accidental_mode: AccidentalMode,
) -> None:
    if event.kind == "rest":
        body_offset = token.find("0")
        for source_id in event.source_roles.get("note", []):
            _append_anchor(
                anchors,
                seen,
                source_id,
                absolute_start + body_offset,
                absolute_start + body_offset + 1,
                "rest",
            )
    else:
        pitch_cursor = 0
        for pitch in event.pitches:
            pitch_token = _pitch_to_token(pitch, accidental_mode=accidental_mode)
            pitch_offset = token.find(pitch_token, pitch_cursor)
            if pitch_offset < 0:
                continue
            degree_match = re.search(r"[1-7]", pitch_token)
            if degree_match and pitch.source_id:
                start = absolute_start + pitch_offset + degree_match.start()
                _append_anchor(anchors, seen, pitch.source_id, start, start + 1, "note")
            if pitch.accidental_source_id:
                accidental_span = _accidental_span(pitch_token)
                if accidental_span:
                    _append_anchor(
                        anchors,
                        seen,
                        pitch.accidental_source_id,
                        absolute_start + pitch_offset + accidental_span[0],
                        absolute_start + pitch_offset + accidental_span[1],
                        "accidental",
                    )
            pitch_cursor = pitch_offset + len(pitch_token)

    if event.slur_start:
        offset = token.find("(")
        if offset >= 0:
            for source_id in event.source_roles.get("slur_start", []):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + offset,
                    absolute_start + offset + 1,
                    "slur",
                )
    if event.slur_stop:
        offset = token.rfind(")")
        if offset >= 0:
            for source_id in event.source_roles.get("slur_stop", []):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + offset,
                    absolute_start + offset + 1,
                    "slur",
                )

    prefix = line[segment_start:token_start]
    prefix_base = absolute_start - (token_start - segment_start)
    _append_prefix_role_anchors(
        anchors,
        seen,
        event,
        prefix,
        prefix_base,
    )


def _append_prefix_role_anchors(
    anchors: list[TextAnchor],
    seen: set[tuple[str, int, int, str]],
    event: Event,
    prefix: str,
    absolute_start: int,
) -> None:
    search_from = 0
    if event.dynamic:
        dynamic_token = f"\\{event.dynamic}"
        offset = prefix.find(dynamic_token, search_from)
        if offset >= 0:
            for source_id in event.source_roles.get("dynamic", []):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + offset,
                    absolute_start + offset + len(dynamic_token),
                    "dynamic",
                )
            search_from = offset + len(dynamic_token)

    role_marks = (
        ("articulation", list(event.articulations)),
        ("ornament", list(event.ornaments)),
        ("technical", list(event.technical)),
    )
    for role, marks in role_marks:
        sources = event.source_roles.get(role, [])
        for source_id, mark in zip(sources, marks):
            mark_text = _mark_token(mark)
            if not mark_text:
                continue
            rendered = f"^{mark_text}"
            offset = prefix.find(rendered, search_from)
            if offset < 0:
                offset = prefix.find(rendered)
            if offset < 0:
                continue
            _append_anchor(
                anchors,
                seen,
                source_id,
                absolute_start + offset,
                absolute_start + offset + len(rendered),
                role,
            )
            search_from = offset + len(rendered)


def _accidental_span(token: str) -> tuple[int, int] | None:
    degree = re.search(r"[1-7]", token)
    if degree is None:
        return None
    if degree.start() > 0:
        return (0, degree.start())
    suffix = re.search(r"(?:bb|x|#|b)$", token)
    if suffix:
        return suffix.span()
    return None


def _advance_past_text_tokens(line: str, cursor: int, *, count: int = 1) -> int:
    current = cursor
    for _index in range(max(1, count)):
        match = re.search(r"\S+", line[current:])
        if match is None:
            return len(line)
        current += match.end()
    return current


def _rendered_event_token_count(event: Event) -> int:
    count = 1
    if event.dynamic:
        count += 1
    all_marks = list(
        event.articulations or ([event.articulation] if event.articulation else [])
    )
    count += sum(
        1
        for mark in event_mark_ids(
            all_marks,
            list(event.ornaments),
            list(event.technical),
        )
        if _mark_token(mark)
    )
    if event.slide_stop:
        count += 1
    return count


def _append_anchor(
    anchors: list[TextAnchor],
    seen: set[tuple[str, int, int, str]],
    source_id: str,
    start: int,
    end: int,
    role: str,
) -> None:
    if start < 0 or end <= start:
        return
    key = (source_id, start, end, role)
    if key in seen:
        return
    seen.add(key)
    anchors.append(
        TextAnchor(
            source_id=source_id,
            start_utf16=start,
            end_utf16=end,
            role=role,
        )
    )


def _utf16_offset(text: str, offset: int) -> int:
    return len(text[:offset].encode("utf-16-le")) // 2


def _event_to_token(
    event: Event,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    prefix, suffix = _duration_parts(event.duration)
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [
            _pitch_to_token(pitch, accidental_mode=accidental_mode)
            for pitch in event.pitches
        ]
        body = (
            "[" + "+".join(tokens) + "]"
            if len(tokens) > 1
            else tokens[0]
            if tokens
            else "?"
        )
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


def _collect_tuplet_events(events: list[Event], start_index: int) -> list[Event]:
    first = events[start_index]
    group = [first]
    tuplet_id = first.tuplet_id
    declared_count = max(1, first.tuplet_count or 1)
    for event in events[start_index + 1 :]:
        if tuplet_id is None:
            if len(group) >= declared_count:
                break
            if event.tuplet_id is not None:
                break
        elif event.tuplet_id != tuplet_id:
            break
        group.append(event)
        if event.tuplet_stop:
            break
    return group


def _tuplet_to_token(
    events: list[Event],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    actual_count = events[0].tuplet_count or len(events)
    normal_count = events[0].tuplet_normal_count or _tuplet_normal_notes(actual_count)
    legacy_duration = all(
        event.duration == Fraction(1, actual_count) for event in events
    )
    notated_durations = [
        event.duration * Fraction(actual_count, normal_count) for event in events
    ]
    parts = [
        _event_to_tuplet_body(
            event,
            accidental_mode=accidental_mode,
            include_duration=not legacy_duration,
            actual_count=actual_count,
            normal_count=normal_count,
        )
        for event in events
    ]
    if all(re.fullmatch(r"(?:bb|x|n|♮|#|b)?[0-7][',]*[#b]?", part) for part in parts):
        body = "".join(parts)
    else:
        body = " ".join(parts)
    implicit_ratio = actual_count == len(
        events
    ) and normal_count == _tuplet_normal_notes(len(events))
    has_visible_duration_prefix = any(
        duration_affixes(duration)[0] for duration in notated_durations
    )
    ratio_prefix = (
        f"{actual_count}:{normal_count};"
        if not implicit_ratio
        or (not legacy_duration and not has_visible_duration_prefix)
        else ""
    )
    return f"${ratio_prefix}{body}$"


def _event_to_tuplet_body(
    event: Event,
    *,
    accidental_mode: AccidentalMode = "auto",
    include_duration: bool = False,
    actual_count: int = 1,
    normal_count: int = 1,
) -> str:
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [
            _pitch_to_token(pitch, accidental_mode=accidental_mode)
            for pitch in event.pitches
        ]
        body = (
            "[" + "+".join(tokens) + "]"
            if len(tokens) > 1
            else tokens[0]
            if tokens
            else "?"
        )
    if include_duration:
        notated_duration = event.duration * Fraction(actual_count, normal_count)
        duration_prefix, duration_suffix = duration_affixes(notated_duration)
        body = duration_prefix + body + duration_suffix
    if event.tie_stop:
        body = "~" + body
    if event.slur_start:
        body = "(" + body
    if event.slur_stop:
        body = body + ")"
    if event.tie_start:
        body = body + "~"
    prefixes: list[str] = []
    if event.dynamic:
        prefixes.append(f"\\{event.dynamic}")
    all_marks = list(
        event.articulations or ([event.articulation] if event.articulation else [])
    )
    for mark in event_mark_ids(
        all_marks,
        list(event.ornaments),
        list(event.technical),
    ):
        token = _mark_token(mark)
        if token:
            prefixes.append(f"^{token}")
    if event.slide_stop:
        prefixes.append(f"^{_CONTINUOUS_SLIDE_TOKEN}")
    body = "".join(prefixes) + body
    return body


def _tuplet_normal_notes(actual_notes: int) -> int:
    normal_notes = 1
    while normal_notes * 2 <= actual_notes:
        normal_notes *= 2
    return max(1, normal_notes)


def _duration_parts(duration: Fraction) -> tuple[str, str]:
    return duration_affixes(duration)


def _mark_token(name: str) -> str | None:
    return mark_token(name)


def _pitch_to_token(
    pitch: JianpuPitch,
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return pitch_to_token(pitch, accidental_mode=accidental_mode)
