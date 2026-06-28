from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re

from ..jianpu_tokens import DURATION_PREFIXES, consume_duration_prefix
from ..constants import DYNAMICS
from ..performance_marks import (
    PERFORMANCE_MARKS,
    mark_for_token,
    normalize_event_marks,
)
from ...models.common.types import InstrumentProfile
from ...models.score import Beat, Event, JianpuPitch, JianpuScore, Measure, TextBlock


@dataclass(slots=True)
class JianpuOptions:
    key: str = "C"
    beats: int = 4
    beat_type: int = 4
    title: str = "简谱"
    tempo: int | None = None
    instrument_profile: InstrumentProfile = "general"


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
        instrument_profile=score.instrument_profile,
    )
    tokens: list[ParsedToken] = []
    for measure in score.measures:
        for event in measure.events:
            if event.kind == "rest":
                tokens.append(ParsedToken("rest", "0", event.duration))
            else:
                pitch = event.pitches[0] if event.pitches else JianpuPitch(1)
                tokens.append(
                    ParsedToken(
                        "note",
                        str(pitch.degree),
                        event.duration,
                        pitch.octave,
                        pitch.accidental,
                    )
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
        instrument_profile=options.instrument_profile,
    )

    current_events: list[Event] = []
    current_blocks: list[TextBlock] = []
    cursor = Fraction(0, 1)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    pending_ornaments: list[str] = []
    pending_technical: list[str] = []
    pending_slide = False
    measure_articulations: list[str] = []
    measure_ornaments: list[str] = []
    pending_repeat_count: int = 1
    open_slur = False
    open_tie = False
    measure_number = 1
    next_repeat_start = False
    current_key = options.key
    current_beats = options.beats
    current_beat_type = options.beat_type
    last_pitched_event: Event | None = None

    def flush_measure() -> None:
        nonlocal \
            current_events, \
            current_blocks, \
            cursor, \
            measure_number, \
            next_repeat_start, \
            measure_articulations, \
            measure_ornaments, \
            pending_repeat_count
        if not current_events and not current_blocks:
            measure_articulations = []
            measure_ornaments = []
            return
        measure = Measure(
            source_number=str(measure_number),
            duration=Fraction(current_beats * 4, current_beat_type),
            events=current_events,
            text_blocks=current_blocks,
            beats_per_measure=current_beats,
            beat_type=current_beat_type,
            source_key=current_key,
            target_key=current_key,
            repeat_start=next_repeat_start,
            repeat_count=pending_repeat_count,
        )
        _normalize_parsed_measure(measure)
        score.measures.append(measure)
        current_events = []
        current_blocks = []
        cursor = Fraction(0, 1)
        measure_number += 1
        next_repeat_start = False
        measure_articulations = []
        measure_ornaments = []
        pending_repeat_count = 1

    def append_event(event: Event, raw: str) -> None:
        nonlocal \
            cursor, \
            pending_dynamic, \
            pending_articulations, \
            pending_ornaments, \
            pending_technical, \
            pending_slide, \
            open_slur, \
            open_tie, \
            last_pitched_event
        event.source_token = raw
        event.start = cursor
        if pending_dynamic:
            event.dynamic = pending_dynamic
            pending_dynamic = None
        event_articulations = list(
            event.articulations or ([event.articulation] if event.articulation else [])
        )
        event_ornaments = list(event.ornaments)
        event_technical = list(event.technical)
        if event.kind == "note":
            event_articulations = _unique_marks(
                event_articulations, measure_articulations, pending_articulations
            )
            event_ornaments = _unique_marks(
                event_ornaments, measure_ornaments, pending_ornaments
            )
            event_technical = _unique_marks(event_technical, pending_technical)
        else:
            event_articulations = _unique_marks(
                event_articulations, pending_articulations
            )
            event_ornaments = _unique_marks(event_ornaments, pending_ornaments)
            event_technical = _unique_marks(event_technical, pending_technical)
        if event_articulations:
            event.articulations = event_articulations
            event.articulation = event_articulations[0]
        if event_ornaments:
            event.ornaments = event_ornaments
        if event_technical:
            event.technical = event_technical
        pending_articulations = []
        pending_ornaments = []
        pending_technical = []
        if pending_slide:
            event.slide_stop = True
            pending_slide = False
        if event.slide_stop:
            if event.kind != "note":
                raise ValueError("连线滑音 ^lh 后必须跟随音符，不能跟休止符")
            if last_pitched_event is None:
                raise ValueError("连线滑音 ^lh 前没有可连接的起始音")
            last_pitched_event.slide_start = True
        if raw.startswith("("):
            event.slur_start = True
            open_slur = True
        if raw.endswith(")") and open_slur:
            event.slur_stop = True
            open_slur = False
        # Propagate tie across measures: if a previous note had tie_start,
        # the next note automatically receives tie_stop even without explicit ~
        if open_tie and not event.tie_stop:
            event.tie_stop = True
        if event.tie_start:
            open_tie = True
        elif event.tie_stop:
            open_tie = False
        current_events.append(event)
        cursor += event.duration
        if event.kind == "note":
            last_pitched_event = event
        normalize_event_marks(event)

    for token in token_lines:
        raw = token.value
        key_signature = _key_signature_value(raw)
        if key_signature is not None:
            if current_events:
                raise _syntax_error(
                    token,
                    f"调号 {raw} 必须写在该小节音符之前，不能写在音符后面。"
                    "请把调号移到小节开头或紧跟在小节线 | 之后。",
                )
            current_key = key_signature
            continue
        time_signature = _time_signature_value(raw)
        if time_signature is not None:
            if current_events:
                raise _syntax_error(
                    token,
                    f"拍号 {raw} 必须写在该小节音符之前，不能写在音符后面。"
                    "请把拍号移到小节开头或紧跟在小节线 | 之后。",
                )
            current_beats, current_beat_type = time_signature
            continue
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
        if re.fullmatch(r"\*\d+", raw):
            pending_repeat_count = max(1, int(raw[1:]))
            continue

        measure_mark = _measure_level_mark(raw)
        if measure_mark is not None:
            kind, mark = measure_mark
            if not mark:
                raise _syntax_error(
                    token,
                    f"不支持的小节级演奏标记：{raw}。"
                    "请使用 (^l)、(^.)、(^>)、(^r)、(^f)",
                )
            if current_events:
                raise _syntax_error(
                    token,
                    f"小节级演奏标记 {raw} 必须写在当前小节第一个音符或休止符之前。",
                )
            if kind == "ornament":
                _append_unique_mark(measure_ornaments, mark)
            else:
                _append_unique_mark(measure_articulations, mark)
            continue
        if raw.startswith("\\"):
            dynamic = raw[1:]
            if dynamic not in DYNAMICS:
                raise _syntax_error(
                    token, f"不支持的力度标记：{raw}，请使用 \\p、\\mp、\\f、\\ff 等"
                )
            pending_dynamic = dynamic
            continue
        if raw.startswith("^"):
            name = raw[1:]
            if name == "lh":
                pending_slide = True
                continue
            kind, mark = _mark_kind_name(name)
            if kind == "ornament":
                pending_ornaments.append(mark)
            elif kind == "technical":
                pending_technical.append(mark)
            else:
                pending_articulations.append(mark)
            continue
        if raw.startswith("$") and raw.endswith("$"):
            for event, source_token in _parse_tuplet_token(token):
                append_event(event, source_token)
            continue

        append_event(_parse_event_token(token), raw)

    if pending_slide:
        raise ValueError("连线滑音 ^lh 后必须跟随目标音符")
    if current_events or current_blocks or not score.measures:
        flush_measure()

    _apply_lyrics(score, lyrics)
    current_number = 1
    for measure in score.measures:
        measure.display_number = current_number
        current_number += measure.repeat_count
    return score


def _read_new_syntax(text: str) -> tuple[JianpuOptions, list[_Token], list[str]]:
    options = JianpuOptions()
    tokens: list[_Token] = []
    lyrics: list[str] = []
    saw_time = False
    saw_score_tokens = False
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        raw_line = _strip_inline_comment(raw_line)
        stripped = raw_line.strip()
        if not stripped:
            continue
        raw_line = _strip_leading_measure_label(raw_line)
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("L:"):
            lyrics.extend(part for part in stripped[2:].strip().split() if part)
            continue
        if "=" in stripped and not stripped.startswith(("|", ":", "[", "\\", "^", "$")):
            key, value = [part.strip() for part in stripped.split("=", 1)]
            if key == "1" and _is_key_name(value):
                if saw_score_tokens:
                    tokens.append(
                        _Token(stripped, line_no, raw_line.find(stripped) + 1)
                    )
                else:
                    options.key = value
                continue
            if key == "title":
                options.title = value or options.title
                continue
            if key == "tempo":
                options.tempo = int(value)
                continue
            if key == "instrument":
                if value not in {"general", "erhu", "zhongruan"}:
                    raise ValueError(
                        f"第 {line_no} 行：不支持的乐器模式 {value}，"
                        "请使用 general、erhu 或 zhongruan"
                    )
                options.instrument_profile = value
                continue
        if re.fullmatch(r"\d+/\d+", stripped) and not saw_time:
            beats, beat_type = stripped.split("/", 1)
            if saw_score_tokens:
                tokens.append(_Token(stripped, line_no, raw_line.find(stripped) + 1))
            else:
                options.beats = int(beats)
                options.beat_type = int(beat_type)
                saw_time = True
            continue
        for match in re.finditer(r"\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+", raw_line):
            raw_token = match.group(0)
            if _is_measure_label_token(raw_token):
                continue
            tokens.append(_Token(raw_token, line_no, match.start() + 1))
            if not _is_key_or_time_token(raw_token):
                saw_score_tokens = True
    return options, tokens, lyrics


def _is_key_or_time_token(token: str) -> bool:
    return (
        _key_signature_value(token) is not None
        or _time_signature_value(token.strip()) is not None
    )


def _strip_inline_comment(line: str) -> str:
    comment_start = line.find("//")
    if comment_start < 0:
        return line
    return line[:comment_start]


def _strip_leading_measure_label(line: str) -> str:
    return re.sub(r"^\s*\d+[.:：]\s*", "", line, count=1)


def _is_measure_label_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+[.:：]", token.strip()))


def _key_signature_value(token: str) -> str | None:
    match = re.fullmatch(r"1\s*=\s*([A-G](?:#|b)?)", token.strip())
    return match.group(1) if match else None


def _time_signature_value(token: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d+)/(\d+)", token.strip())
    if not match:
        return None
    beats = int(match.group(1))
    beat_type = int(match.group(2))
    if beats <= 0 or beat_type <= 0:
        return None
    return beats, beat_type


def _is_key_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-G](?:#|b)?", value.strip()))


def _parse_tuplet_token(token: _Token) -> list[tuple[Event, str]]:
    body = token.value.strip()[1:-1].strip()
    parts = _split_tuplet_body(body)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    pending_ornaments: list[str] = []
    pending_technical: list[str] = []
    parsed: list[tuple[Event, str]] = []
    for part in parts:
        mark = _tuplet_standalone_mark(part)
        if mark is not None:
            kind, name = mark
            if kind == "dynamic":
                pending_dynamic = name
            elif kind == "ornament":
                _append_unique_mark(pending_ornaments, name)
            elif kind == "technical":
                _append_unique_mark(pending_technical, name)
            elif kind == "slide":
                pending_technical.append("__slide_from_previous__")
            else:
                _append_unique_mark(pending_articulations, name)
            continue
        inline_marks, event_part = _consume_tuplet_inline_marks(part)
        if not event_part:
            raise _syntax_error(token, f"连音组标记 {part} 后面必须跟随音符或休止符")
        part_token = _Token(event_part, token.line, token.column + 1 + body.find(part))
        event = _parse_event_token(part_token)
        inline_articulations = [
            name for kind, name in inline_marks if kind == "articulation"
        ]
        inline_ornaments = [name for kind, name in inline_marks if kind == "ornament"]
        inline_technical = [
            name for kind, name in inline_marks if kind == "technical"
        ]
        has_slide = "__slide_from_previous__" in pending_technical or any(
            kind == "slide" for kind, _name in inline_marks
        )
        inline_dynamic = next(
            (name for kind, name in reversed(inline_marks) if kind == "dynamic"),
            None,
        )
        if inline_dynamic or pending_dynamic:
            event.dynamic = inline_dynamic or pending_dynamic
        event_articulations = list(
            event.articulations or ([event.articulation] if event.articulation else [])
        )
        event_articulations = _unique_marks(
            event_articulations,
            pending_articulations,
            inline_articulations,
        )
        if event_articulations:
            event.articulations = event_articulations
            event.articulation = event_articulations[0]
        event.ornaments = _unique_marks(
            list(event.ornaments),
            pending_ornaments,
            inline_ornaments,
        )
        event.technical = _unique_marks(
            list(event.technical),
            [
                mark
                for mark in pending_technical
                if mark != "__slide_from_previous__"
            ],
            inline_technical,
        )
        event.slide_stop = has_slide
        normalize_event_marks(event)
        pending_dynamic = None
        pending_articulations = []
        pending_ornaments = []
        pending_technical = []
        parsed.append((event, event_part))
    if len(parsed) < 2:
        raise _syntax_error(token, "连音组至少需要两个音符，例如 $123$ 或 $1 2 3$")
    duration = Fraction(1, len(parsed))
    group_id = f"{token.line}:{token.column}"
    events: list[tuple[Event, str]] = []
    for index, (event, source_token) in enumerate(parsed):
        event.duration = duration
        event.dotted = 0
        event.tuplet_id = group_id
        event.tuplet_count = len(parsed)
        event.tuplet_index = index
        event.tuplet_start = index == 0
        event.tuplet_stop = index == len(parsed) - 1
        events.append((event, source_token))
    return events


def _split_tuplet_body(body: str) -> list[str]:
    if not body:
        return []
    if re.search(r"\s", body):
        return [part for part in body.split() if part]
    parts: list[str] = []
    index = 0
    while index < len(body):
        start = index
        index = _consume_tuplet_mark_prefix(body, index)
        match = re.match(
            r"~?\(?(?:bb|x|n|♮|#|b)?[0-7][',]*(?:#|b)?\.?-*\)?~?", body[index:]
        )
        if match is None or not match.group(0):
            return [body]
        index += match.end()
        parts.append(body[start:index])
    return parts


def _consume_tuplet_mark_prefix(body: str, index: int) -> int:
    while index < len(body):
        if body.startswith("^", index) and index + 1 < len(body):
            token = _match_mark_token(body[index + 1 :])
            if token:
                index += len(token) + 1
                continue
        if body.startswith("\\", index):
            dynamic = _match_dynamic_prefix(body[index + 1 :])
            if dynamic:
                index += len(dynamic) + 1
                continue
        break
    return index


def _tuplet_standalone_mark(part: str) -> tuple[str, str] | None:
    if part.startswith("\\"):
        dynamic = part[1:]
        if dynamic in DYNAMICS:
            return "dynamic", dynamic
        return None
    if part.startswith("^"):
        raw = part[1:]
        if raw == "lh":
            return "slide", "continuous-slide"
        if mark_for_token(raw):
            return _mark_kind_name(raw)
    return None


def _consume_tuplet_inline_marks(part: str) -> tuple[list[tuple[str, str]], str]:
    marks: list[tuple[str, str]] = []
    work = part.strip()
    while work:
        if work.startswith("^") and len(work) > 1:
            raw = _match_mark_token(work[1:])
            if raw:
                if raw == "lh":
                    marks.append(("slide", "continuous-slide"))
                else:
                    marks.append(_mark_kind_name(raw))
                work = work[len(raw) + 1 :]
                continue
        if work.startswith("\\"):
            dynamic = _match_dynamic_prefix(work[1:])
            if dynamic:
                marks.append(("dynamic", dynamic))
                work = work[len(dynamic) + 1 :]
                continue
        break
    return marks, work


def _match_dynamic_prefix(value: str) -> str | None:
    for dynamic in sorted(DYNAMICS, key=len, reverse=True):
        if value.startswith(dynamic):
            return dynamic
    return None


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
    has_duration_prefix = bool(work) and work[0] in DURATION_PREFIXES
    duration, work = _consume_duration_prefix(work)
    if has_duration_prefix and work.startswith("."):
        raise _syntax_error(
            token,
            f"时值前缀后的附点 `{token.value}` 非法，附点必须写在音级之后，例如 h4'. 而不是 h.4'",
        )
    while work.endswith("-"):
        duration += Fraction(1, 1)
        work = work[:-1]
    dotted = work.endswith(".")
    if dotted:
        duration += duration / 2
        work = work[:-1]
    if work.startswith("[") and work.endswith("]"):
        parts = [part.strip() for part in work[1:-1].split("+") if part.strip()]
        if not parts:
            raise _syntax_error(token, "和弦不能为空，请写成 [1+3+5]")
        event = Event(
            kind="note",
            duration=duration,
            pitches=[_parse_pitch(part, token) for part in parts],
        )
        event.pitches.sort(key=lambda pitch: pitch.rank, reverse=True)
    elif work == "0":
        event = Event(kind="rest", duration=duration)
    else:
        event = Event(
            kind="note", duration=duration, pitches=[_parse_pitch(work, token)]
        )
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
    return JianpuPitch(
        int(value),
        octave=octave,
        accidental=accidental,
        accidental_text=accidental_text,
    )


def _consume_duration_prefix(token: str) -> tuple[Fraction, str]:
    return consume_duration_prefix(token)


def _normalize_parsed_measure(measure: Measure) -> None:
    target = Fraction(measure.beats_per_measure * 4, measure.beat_type)
    beat_duration = Fraction(4, measure.beat_type)
    measure.duration = target
    measure.beats = [
        Beat(index=i + 1, duration=beat_duration, start=i * beat_duration)
        for i in range(measure.beats_per_measure)
    ]
    cursor = Fraction(0, 1)
    for event in measure.events:
        if event.start is None:
            event.start = cursor
        beat_index = min(
            measure.beats_per_measure - 1, max(0, int(event.start / beat_duration))
        )
        measure.beats[beat_index].events.append(event)
        cursor = event.start + event.duration
    if measure.span_duration > target:
        measure.validation_errors.append(
            f"小节超拍：实际 {measure.span_duration}，目标 {target}"
        )


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
        "r": "trill-mark",
        "f": "fermata",
    }.get(raw, raw)


def _ornament_name(raw: str) -> str | None:
    normalized = raw.strip().lower()
    if normalized == "l":
        return "tremolo"
    return None


def _measure_level_mark(raw: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\(\^([A-Za-z0-9.>\-]{1,2})\)", raw)
    if match is None:
        if raw.startswith("(^") and raw.endswith(")"):
            return "invalid", ""
        return None
    raw_name = match.group(1)
    mark = mark_for_token(raw_name)
    if mark is None or not mark.measure_scope:
        return "invalid", ""
    return mark.category, mark.id


def _mark_kind_name(raw: str) -> tuple[str, str]:
    mark = mark_for_token(raw)
    if mark is not None:
        return mark.category, mark.id
    ornament = _ornament_name(raw)
    if ornament:
        return "ornament", ornament
    return "articulation", _articulation_name(raw)


_MARK_TOKENS = tuple(
    sorted(
        {mark.token for mark in PERFORMANCE_MARKS} | {"lh"},
        key=len,
        reverse=True,
    )
)


def _match_mark_token(value: str) -> str | None:
    return next((token for token in _MARK_TOKENS if value.startswith(token)), None)


def _append_unique_mark(target: list[str], mark: str) -> None:
    if mark not in target:
        target.append(mark)


def _unique_marks(*mark_groups: list[str]) -> list[str]:
    result: list[str] = []
    for group in mark_groups:
        for mark in group:
            _append_unique_mark(result, mark)
    return result


def _syntax_error(token: _Token, message: str) -> ValueError:
    return ValueError(f"第 {token.line} 行第 {token.column} 列：{message}")
