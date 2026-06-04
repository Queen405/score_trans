from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re

from ..jianpu_tokens import consume_duration_prefix
from ..constants import DYNAMICS
from ...models.score import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock


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
    normalized = text
    options, token_lines, lyrics = _read_new_syntax(normalized)
    if title and options.title == "简谱":
        options.title = title
    score = JianpuScore(
        title=options.title,
        target_key=options.key,
        source_key=options.key,
        beats=options.beats,
        beat_type=options.beat_type,
    )

    current_events: list[Event] = []
    current_blocks: list[TextBlock] = []
    cursor = Fraction(0, 1)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    open_slur = False
    measure_number = 1
    next_repeat_start = False

    def flush_measure() -> None:
        nonlocal current_events, current_blocks, cursor, measure_number, next_repeat_start
        if not current_events and not current_blocks:
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
            repeat_start=next_repeat_start,
        )
        _normalize_parsed_measure(measure, score)
        score.measures.append(measure)
        current_events = []
        current_blocks = []
        cursor = Fraction(0, 1)
        measure_number += 1
        next_repeat_start = False

    for token in token_lines:
        raw = token.value
        if raw in {"|", "||"}:
            flush_measure()
            continue
        if raw == "|:":
            flush_measure()
            next_repeat_start = True
            continue
        if raw == ":|":
            flush_measure()
            if score.measures:
                score.measures[-1].repeat_end = True
            continue
        if raw.startswith("\\"):
            dynamic = raw[1:]
            if dynamic not in DYNAMICS:
                raise _syntax_error(token, f"不支持的力度标记：{raw}，请使用 \\p、\\mp、\\f、\\ff 等")
            pending_dynamic = dynamic
            continue
        if raw.startswith("^"):
            pending_articulations.append(_articulation_name(raw[1:]))
            continue

        event = _parse_event_token(token)
        event.source_token = raw
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


def _read_new_syntax(text: str) -> tuple[JianpuOptions, list[_Token], list[str]]:
    options = JianpuOptions()
    tokens: list[_Token] = []
    lyrics: list[str] = []
    saw_time = False
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        raw_line = _strip_leading_measure_label(raw_line)
        stripped = raw_line.strip()
        if not stripped:
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
            raw_token = match.group(0)
            if _is_measure_label_token(raw_token):
                continue
            if saw_time and re.fullmatch(r"\d+/\d+", raw_token.strip()):
                continue
            tokens.append(_Token(raw_token, line_no, match.start() + 1))
    return options, tokens, lyrics


def _strip_leading_measure_label(line: str) -> str:
    return re.sub(r"^\s*\d+[.:：]\s*", "", line, count=1)


def _is_measure_label_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+[.:：]", token.strip()))


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
        raise _syntax_error(
            token,
            f"不支持的简谱 token：{token.value}，请使用 1-7、0、#1、q1、[1+3+5] 等新语法",
        )
    return JianpuPitch(int(value), octave=octave, accidental=accidental, accidental_text=accidental_text)


def _consume_duration_prefix(token: str) -> tuple[Fraction, str]:
    return consume_duration_prefix(token)


def _normalize_parsed_measure(measure: Measure, score: JianpuScore) -> None:
    target = score.measure_duration
    beat_duration = score.beat_duration
    measure.duration = target
    measure.beats = [
        Beat(index=i + 1, duration=beat_duration, start=i * beat_duration)
        for i in range(score.beats)
    ]
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
                TextBlock(
                    text=lyrics[lyric_index],
                    role="lyric",
                    measure_number=measure.display_number,
                    start=event.start,
                )
            )
            lyric_index += 1


def _articulation_name(raw: str) -> str:
    return {
        ">": "accent",
        "-": "tenuto",
        ".": "staccato",
        "tr": "trill-mark",
    }.get(raw, raw)


def _syntax_error(token: _Token, message: str) -> ValueError:
    return ValueError(f"第 {token.line} 行第 {token.column} 列：{message}")
