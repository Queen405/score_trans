from __future__ import annotations

import hashlib
import json
import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction

from ...models.common.types import AccidentalMode, normalize_instrument_profile
from ...models.provenance.entities import JianpuDocument
from ...models.provenance.schemas import TextAnchor
from ...models.score import DEFAULT_TEMPO, Event, JianpuScore, Measure
from ..accidentals import pitch_to_token
from ..constants import DYNAMICS
from ..jianpu_tokens import (
    safe_duration_affixes,
    tuplet_normal_notes,
)
from ..performance_marks import event_mark_ids, mark_token

_CONTINUOUS_SLIDE_TOKEN = mark_token("continuous-slide") or "lh"
logger = logging.getLogger(__name__)


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
    serializable_score = _score_with_serializable_slurs(score)
    text = _score_to_jianpu_text(serializable_score, accidental_mode=accidental_mode)
    return JianpuDocument(
        text=text,
        anchors=_text_anchors(
            serializable_score,
            text,
            accidental_mode=accidental_mode,
        ),
        text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def scores_to_jianpu_text(
    scores: list[JianpuScore],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    return scores_to_jianpu_document(scores, accidental_mode=accidental_mode).text


def _resolve_multi_voice(scores: list[JianpuScore]) -> list[JianpuScore]:
    """同声部多 voice 处理：拍平为单声部输出并警告。

    简谱文本无 voice 级表达。Audiveris 等 OMR 常把单声部旋律伪拆成多个 voice
    （甚至用 ``<backup>`` 造成时间重叠），硬拦截会阻断整个识别流程，故沿用旧的
    「拍平」行为：由 ``_events_grouped_by_voice`` 按 voice 分组排序后输出单声部
    文本，同时通过警告日志提示真复调可能丢失信息。真复调若有损需要，应由调用方
    显式按 ``// @part`` 拆分各 voice。
    """
    for score in scores:
        voices = _collect_voices(score)
        if len(voices) > 1:
            name = score.part_name or f"声部{score.part_index + 1}"
            logger.warning(
                "声部「%s」包含 %d 个 voice，简谱文本无 voice 表达，已拍平为单声部输出"
                "（真复调可能有损）；若需无损请将各 voice 拆分为独立声部（// @part）。",
                name,
                len(voices),
            )
    return scores


def _collect_voices(score: JianpuScore) -> set[str]:
    voices: set[str] = set()
    for measure in score.measures:
        for event in measure.events:
            if event.kind in ("note", "rest") and event.voice:
                voices.add(event.voice.strip())
    return voices


def scores_to_jianpu_document(
    scores: list[JianpuScore],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> JianpuDocument:
    if not scores:
        return score_to_jianpu_document(JianpuScore(), accidental_mode=accidental_mode)

    scores = _resolve_multi_voice(scores)
    scores = [_score_with_serializable_slurs(score) for score in scores]

    has_page_info = any(s.page_input_file_name for s in scores) or (
        scores[0].page_count > 1 if scores else False
    )

    part_anchors: list[list[TextAnchor]] = []
    part_offsets: list[int] = []

    full_text = ""
    current_page_index = -1
    part_in_page = 0
    for index, score in enumerate(scores):
        part_text = _score_to_jianpu_text(score, accidental_mode=accidental_mode)
        part_anchors.append(
            _text_anchors_raw(score, part_text, accidental_mode=accidental_mode)
        )
        if has_page_info and score.page_index != current_page_index:
            page_number = score.page_index + 1
            name_suffix = ""
            if score.page_input_file_name:
                name_suffix = f" name={json.dumps(score.page_input_file_name, ensure_ascii=False)}"
            full_text += f"// @page {page_number}{name_suffix}\n"
            current_page_index = score.page_index
            part_in_page = 0
        part_in_page += 1
        encoded_name = json.dumps(score.part_name, ensure_ascii=False)
        marker = f"// @part {part_in_page} name={encoded_name}"
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


def _score_with_serializable_slurs(score: JianpuScore) -> JianpuScore:
    adjusted = deepcopy(score)
    pending_start: Event | None = None
    dropped_starts = 0
    dropped_stops = 0

    for measure in adjusted.measures:
        measure.events = _events_grouped_by_voice(measure.events)
        for event in measure.events:
            if event.kind == "note" and not event.pitches:
                logger.warning(
                    "小节 %s 含无音高 note，简谱文本按休止符输出",
                    measure.source_number,
                )
                event.kind = "rest"
            if event.dynamic and event.dynamic not in DYNAMICS:
                logger.warning(
                    "小节 %s 含不支持的力度 %s，简谱文本已忽略",
                    measure.source_number,
                    event.dynamic,
                )
                event.dynamic = None
            if event.kind == "rest" and event.hidden:
                continue
            source_start = event.slur_start
            source_stop = event.slur_stop
            event.slur_start = False
            event.slur_stop = False

            if source_stop:
                if pending_start is None:
                    dropped_stops += 1
                else:
                    pending_start.slur_start = True
                    event.slur_stop = True
                    pending_start = None

            if source_start:
                if pending_start is not None or event.slur_stop:
                    dropped_starts += 1
                else:
                    pending_start = event

    if pending_start is not None:
        dropped_starts += 1
    if dropped_starts or dropped_stops:
        logger.warning(
            "简谱文本仅支持非嵌套连音线，已忽略 %d 个起点和 %d 个终点",
            dropped_starts,
            dropped_stops,
        )
    return adjusted


def _events_grouped_by_voice(events: list[Event]) -> list[Event]:
    def key(item: tuple[int, Event]) -> tuple[int, int | str, Fraction, int]:
        index, event = item
        voice = (event.voice or "1").strip()
        voice_key: tuple[int, int | str] = (
            (0, int(voice)) if voice.isdigit() else (1, voice)
        )
        return (*voice_key, event.start or Fraction(0, 1), index)

    return [event for _index, event in sorted(enumerate(events), key=key)]


def _measure_lead_info(
    measure: Measure,
    current_key: str,
    current_beats: int,
    current_beat_type: int,
    current_tempo: int | None,
) -> tuple[list[str], str, str, int, int, int | None, str | None]:
    lead_tokens: list[str] = []
    tempo_line: str | None = None
    if measure.tempo is not None and measure.tempo != current_tempo:
        tempo_line = f"tempo={measure.tempo}"
        current_tempo = measure.tempo
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
    return (
        lead_tokens,
        prefix,
        current_key,
        current_beats,
        current_beat_type,
        current_tempo,
        tempo_line,
    )


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
    current_tempo = score.tempo or DEFAULT_TEMPO
    lines = [f"1={current_key}", f"{current_beats}/{current_beat_type}"]
    if score.tempo is not None:
        lines.insert(0, f"tempo={score.tempo}")
    instrument_profile = normalize_instrument_profile(score.instrument_profile)
    if instrument_profile != "general":
        lines.insert(0, f"instrument={instrument_profile}")
    if score.title and score.title != "简谱":
        lines.insert(0, f"title={score.title}")
    measure_lines: list[str] = []
    lyrics: list[str] = []
    for measure in score.measures:
        (
            lead_tokens,
            prefix,
            current_key,
            current_beats,
            current_beat_type,
            current_tempo,
            tempo_line,
        ) = _measure_lead_info(
            measure,
            current_key,
            current_beats,
            current_beat_type,
            current_tempo,
        )
        if tempo_line is not None:
            measure_lines.append(tempo_line)
        events = measure.events
        tokens = []
        index = 0
        while index < len(events):
            event = events[index]
            if event.kind == "rest" and event.hidden and event.tuplet_id is None:
                index += 1
                continue
            if event.tuplet_start and event.tuplet_count:
                group = _collect_tuplet_events(events, index)
                tokens.append(_tuplet_to_token(group, accidental_mode=accidental_mode))
                for group_event in group:
                    if group_event.kind == "note" and group_event.lyric:
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
                token = mark_token(mark)
                if token:
                    tokens.append(f"^{token}")
            if event.slide_stop:
                tokens.append(f"^{_CONTINUOUS_SLIDE_TOKEN}")
            tokens.append(
                _event_to_token(
                    event,
                    accidental_mode=accidental_mode,
                    duration=_text_event_duration(event, measure),
                )
            )
            if event.kind == "note" and event.lyric:
                lyrics.append(event.lyric)
            index += 1
        repeat_count = getattr(measure, "repeat_count", 1)
        repeat_suffix = f" *{repeat_count}" if repeat_count > 1 else ""
        suffix = " :|" if getattr(measure, "repeat_end", False) else ""
        body = " ".join([*lead_tokens, *tokens])
        measure_lines.append(prefix + body + repeat_suffix + suffix + " |")
    lines.extend(measure_lines)
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
    current_tempo = score.tempo or DEFAULT_TEMPO
    tempo_line_count = 0
    for measure in score.measures:
        (
            _lead_tokens,
            _prefix,
            _current_key,
            _current_beats,
            _current_beat_type,
            current_tempo,
            tempo_line,
        ) = _measure_lead_info(
            measure,
            measure.target_key,
            measure.beats_per_measure,
            measure.beat_type,
            current_tempo,
        )
        tempo_line_count += int(tempo_line is not None)
    first_measure_line = (
        len(lines) - len(score.measures) - tempo_line_count - lyric_line_count
    )
    if first_measure_line < 0:
        return []

    anchors: list[TextAnchor] = []
    seen: set[tuple[str, int, int, str]] = set()
    line_offset = sum(len(line) for line in lines[:first_measure_line])
    first_measure = score.measures[0]
    current_key = first_measure.target_key
    current_beats = first_measure.beats_per_measure
    current_beat_type = first_measure.beat_type
    current_tempo = score.tempo or DEFAULT_TEMPO
    line_index = first_measure_line
    for measure_index, measure in enumerate(score.measures):
        (
            lead_tokens,
            prefix,
            current_key,
            current_beats,
            current_beat_type,
            current_tempo,
            tempo_line,
        ) = _measure_lead_info(
            measure,
            current_key,
            current_beats,
            current_beat_type,
            current_tempo,
        )
        if tempo_line is not None:
            line_offset += len(lines[line_index])
            line_index += 1
        line = lines[line_index].rstrip("\r\n")
        event_cursor = _lead_skip_length(lead_tokens, prefix)
        events = measure.events
        index = 0
        while index < len(events):
            event = events[index]
            if event.kind == "rest" and event.hidden and event.tuplet_id is None:
                index += 1
                continue
            if event.tuplet_start and event.tuplet_count:
                group = _collect_tuplet_events(events, index)
                plan = _tuplet_emission_plan(group, accidental_mode=accidental_mode)
                if plan.wrapper:
                    group_open = line.find("$", event_cursor)
                    group_close = (
                        line.find("$", group_open + 1) if group_open >= 0 else -1
                    )
                else:
                    group_open = -1
                    group_close = -1
                for group_event, token in zip(group, plan.bodies):
                    position = line.find(
                        token,
                        event_cursor,
                        group_close if group_close >= 0 else len(line),
                    )
                    if position < 0:
                        if group_close < 0:
                            event_cursor = _advance_past_text_tokens(line, event_cursor)
                        continue
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
                if (
                    plan.external_start is not None
                    and group_open > 0
                    and line[group_open - 1] == "("
                ):
                    for source_id in group[plan.external_start].source_roles.get(
                        "slur_start", []
                    ):
                        _append_anchor(
                            anchors,
                            seen,
                            source_id,
                            line_offset + group_open - 1,
                            line_offset + group_open,
                            "slur",
                        )
                if (
                    plan.external_stop is not None
                    and group_close >= 0
                    and group_close + 1 < len(line)
                    and line[group_close + 1] == ")"
                ):
                    for source_id in group[plan.external_stop].source_roles.get(
                        "slur_stop", []
                    ):
                        _append_anchor(
                            anchors,
                            seen,
                            source_id,
                            line_offset + group_close + 1,
                            line_offset + group_close + 2,
                            "slur",
                        )
                if group_close >= 0:
                    event_cursor = group_close + 1 + int(plan.external_stop is not None)
                index += len(group)
                continue

            token = _event_to_token(
                event,
                accidental_mode=accidental_mode,
                duration=_text_event_duration(event, measure),
            )
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
        line_offset += len(lines[line_index])
        line_index += 1
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
            pitch_token = pitch_to_token(pitch, accidental_mode=accidental_mode)
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
                elif degree_match:
                    # In auto mode, a written accidental can be represented by
                    # the target-key spelling without an explicit #/b/n token.
                    # Keep the source clickable by anchoring it to the pitch
                    # digit instead of reporting it as an unmapped symbol.
                    degree_start = absolute_start + pitch_offset + degree_match.start()
                    _append_anchor(
                        anchors,
                        seen,
                        pitch.accidental_source_id,
                        degree_start,
                        degree_start + 1,
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
    if event.tie_start:
        offset = token.rfind("~")
        if offset >= 0:
            for source_id in _role_sources_with_fallback(
                event, "tie_start", "slur_start"
            ):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + offset,
                    absolute_start + offset + 1,
                    "tie",
                )
    if event.tie_stop:
        offset = token.find("~")
        if offset >= 0:
            for source_id in _role_sources_with_fallback(
                event, "tie_stop", "slur_stop"
            ):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + offset,
                    absolute_start + offset + 1,
                    "tie",
                )

    if event.dotted:
        dot_offsets = [index for index, value in enumerate(token) if value == "."]
        if dot_offsets:
            dot_sources = event.source_roles.get("augmentation_dot", [])
            for dot_offset, source_id in zip(
                dot_offsets, dot_sources[: event.dotted], strict=False
            ):
                _append_anchor(
                    anchors,
                    seen,
                    source_id,
                    absolute_start + dot_offset,
                    absolute_start + dot_offset + 1,
                    "augmentation_dot",
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


def _role_sources_with_fallback(
    event: Event,
    role: str,
    fallback_role: str,
) -> list[str]:
    return event.source_roles.get(role) or event.source_roles.get(fallback_role, [])


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
            mark_text = mark_token(mark)
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
        if mark_token(mark)
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
    duration: Fraction | None = None,
) -> str:
    prefix, suffix = safe_duration_affixes(duration or event.duration)
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [
            pitch_to_token(pitch, accidental_mode=accidental_mode)
            for pitch in event.pitches
        ]
        body = (
            "[" + "+".join(tokens) + "]"
            if len(tokens) > 1
            else tokens[0]
            if tokens
            else "0"
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


def _text_event_duration(event: Event, measure: Measure) -> Fraction:
    if event.kind != "rest":
        return event.duration
    if event.measure_rest:
        return measure.duration
    start = event.start or Fraction(0, 1)
    remaining = measure.duration - start
    if event.duration <= remaining:
        return event.duration
    clamped = remaining if remaining > 0 else min(event.duration, measure.duration)
    logger.warning(
        "小节 %s 的休止时值 %s 超出剩余容量，简谱文本按 %s 输出",
        measure.source_number,
        event.duration,
        clamped,
    )
    return clamped


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


def _tuplet_slur_plan(
    events: list[Event],
) -> tuple[set[int], set[int], int | None, int | None]:
    markers = [
        (index, kind)
        for index, event in enumerate(events)
        for kind, enabled in (
            ("stop", event.slur_stop),
            ("start", event.slur_start),
        )
        if enabled
    ]
    suppressed_starts: set[int] = set()
    suppressed_stops: set[int] = set()
    marker_index = 0
    while marker_index + 1 < len(markers):
        current = markers[marker_index]
        following = markers[marker_index + 1]
        if current[1] == "stop" and following[1] == "start":
            suppressed_stops.add(current[0])
            suppressed_starts.add(following[0])
            marker_index += 2
        else:
            marker_index += 1
    remaining_starts = [
        index
        for index, event in enumerate(events)
        if event.slur_start and index not in suppressed_starts
    ]
    remaining_stops = [
        index
        for index, event in enumerate(events)
        if event.slur_stop and index not in suppressed_stops
    ]
    external_start = (
        remaining_starts[0] if remaining_starts and not remaining_stops else None
    )
    external_stop = (
        remaining_stops[-1] if remaining_stops and not remaining_starts else None
    )
    return suppressed_starts, suppressed_stops, external_start, external_stop


@dataclass(slots=True)
class _TupletEmission:
    form: str
    ratio_prefix: str
    bodies: list[str]
    wrapper: str
    total: Fraction
    suppressed_starts: set[int]
    suppressed_stops: set[int]
    external_start: int | None
    external_stop: int | None


def _tuplet_emission_plan(
    events: list[Event],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> _TupletEmission:
    actual_count = events[0].tuplet_count or len(events)
    normal_count = events[0].tuplet_normal_count or tuplet_normal_notes(actual_count)
    total = sum((event.duration for event in events), Fraction(0))
    legacy = all(event.duration == Fraction(1, actual_count) for event in events)
    uniform = actual_count > 0 and all(
        event.duration == total / actual_count for event in events
    )
    (
        suppressed_starts,
        suppressed_stops,
        external_start,
        external_stop,
    ) = _tuplet_slur_plan(events)
    if len(events) < 2:
        form = "plain"
        ratio_prefix = ""
        include_duration = True
        wrapper = ""
    elif legacy:
        form = "default"
        ratio_prefix = ""
        include_duration = False
        wrapper = "$"
    elif total.denominator == 1 and total >= 1 and uniform:
        form = "ratio"
        ratio_prefix = f"{actual_count}:{int(total)};"
        include_duration = False
        wrapper = "$"
    else:
        form = "degrade"
        ratio_prefix = ""
        include_duration = True
        wrapper = ""
    bodies = [
        _event_to_tuplet_body(
            event,
            accidental_mode=accidental_mode,
            include_duration=include_duration,
            actual_count=actual_count,
            normal_count=normal_count,
            include_slur_start=(
                index not in suppressed_starts and index != external_start
            ),
            include_slur_stop=(
                index not in suppressed_stops and index != external_stop
            ),
        )
        for index, event in enumerate(events)
    ]
    return _TupletEmission(
        form=form,
        ratio_prefix=ratio_prefix,
        bodies=bodies,
        wrapper=wrapper,
        total=total,
        suppressed_starts=suppressed_starts,
        suppressed_stops=suppressed_stops,
        external_start=external_start,
        external_stop=external_stop,
    )


def _tuplet_to_token(
    events: list[Event],
    *,
    accidental_mode: AccidentalMode = "auto",
) -> str:
    plan = _tuplet_emission_plan(events, accidental_mode=accidental_mode)
    if plan.form == "degrade":
        logger.warning(
            "连音组无法用 $...$ 或比例表达（总时值 %s 拍），按普通音符降级输出",
            plan.total,
        )
    if plan.wrapper and all(re.fullmatch(r"[0-7][',]*", body) for body in plan.bodies):
        body = "".join(plan.bodies)
    else:
        body = " ".join(plan.bodies)
    prefix = "(" if plan.external_start is not None else ""
    suffix = ")" if plan.external_stop is not None else ""
    if plan.wrapper:
        return f"{prefix}{plan.wrapper}{plan.ratio_prefix}{body}{plan.wrapper}{suffix}"
    return f"{prefix}{body}{suffix}"


def _event_to_tuplet_body(
    event: Event,
    *,
    accidental_mode: AccidentalMode = "auto",
    include_duration: bool = False,
    actual_count: int = 1,
    normal_count: int = 1,
    include_slur_start: bool = True,
    include_slur_stop: bool = True,
) -> str:
    if event.kind == "rest":
        body = "0"
    else:
        tokens = [
            pitch_to_token(pitch, accidental_mode=accidental_mode)
            for pitch in event.pitches
        ]
        body = (
            "[" + "+".join(tokens) + "]"
            if len(tokens) > 1
            else tokens[0]
            if tokens
            else "0"
        )
    if include_duration:
        notated_duration = event.duration * Fraction(actual_count, normal_count)
        duration_prefix, duration_suffix = safe_duration_affixes(notated_duration)
        body = duration_prefix + body + duration_suffix
    if event.tie_stop:
        body = "~" + body
    if event.slur_start and include_slur_start:
        body = "(" + body
    if event.slur_stop and include_slur_stop:
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
        token = mark_token(mark)
        if token:
            prefixes.append(f"^{token}")
    if event.slide_stop:
        prefixes.append(f"^{_CONTINUOUS_SLIDE_TOKEN}")
    body = "".join(prefixes) + body
    return body
