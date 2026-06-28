from __future__ import annotations

from fractions import Fraction
import re

from ..accidentals import pitch_to_token
from ..jianpu_tokens import duration_affixes
from ..performance_marks import event_mark_ids, mark_token
from ...models.common.types import AccidentalMode
from ...models.score import Event, JianpuPitch, JianpuScore


def score_to_jianpu_text(
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
    if score.instrument_profile != "general":
        lines.insert(0, f"instrument={score.instrument_profile}")
    if score.title and score.title != "简谱":
        lines.insert(0, f"title={score.title}")
    measures = []
    lyrics: list[str] = []
    for measure in score.measures:
        measure_key = getattr(measure, "target_key", current_key)
        measure_beats = getattr(measure, "beats_per_measure", current_beats)
        measure_beat_type = getattr(measure, "beat_type", current_beat_type)
        lead_tokens: list[str] = []
        if measure_key != current_key:
            lead_tokens.append(f"1={measure_key}")
            current_key = measure_key
        if measure_beats != current_beats or measure_beat_type != current_beat_type:
            lead_tokens.append(f"{measure_beats}/{measure_beat_type}")
            current_beats = measure_beats
            current_beat_type = measure_beat_type
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
                tokens.append("^lh")
            tokens.append(_event_to_token(event, accidental_mode=accidental_mode))
            if event.lyric:
                lyrics.append(event.lyric)
            index += 1
        prefix = "|: " if getattr(measure, "repeat_start", False) else ""
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
    for event in events[start_index + 1 :]:
        if tuplet_id is not None and event.tuplet_id != tuplet_id:
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
    parts = [
        _event_to_tuplet_body(event, accidental_mode=accidental_mode)
        for event in events
    ]
    if all(re.fullmatch(r"(?:bb|x|n|♮|#|b)?[0-7][',]*[#b]?", part) for part in parts):
        body = "".join(parts)
    else:
        body = " ".join(parts)
    return f"${body}$"


def _event_to_tuplet_body(
    event: Event,
    *,
    accidental_mode: AccidentalMode = "auto",
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
        prefixes.append("^lh")
    body = "".join(prefixes) + body
    return body


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
