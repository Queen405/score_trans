from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re

from ..jianpu_tokens import DURATION_PREFIXES, consume_duration_prefix
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
    )

    current_events: list[Event] = []
    current_blocks: list[TextBlock] = []
    cursor = Fraction(0, 1)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    pending_ornaments: list[str] = []
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
            open_slur, \
            open_tie
        event.source_token = raw
        event.start = cursor
        if pending_dynamic:
            event.dynamic = pending_dynamic
            pending_dynamic = None
        event_articulations = list(
            event.articulations or ([event.articulation] if event.articulation else [])
        )
        event_ornaments = list(event.ornaments)
        if event.kind == "note":
            event_articulations = _unique_marks(
                event_articulations, measure_articulations, pending_articulations
            )
            event_ornaments = _unique_marks(
                event_ornaments, measure_ornaments, pending_ornaments
            )
        else:
            event_articulations = _unique_marks(
                event_articulations, pending_articulations
            )
            event_ornaments = _unique_marks(event_ornaments, pending_ornaments)
        if event_articulations:
            event.articulations = event_articulations
            event.articulation = event_articulations[0]
        if event_ornaments:
            event.ornaments = event_ornaments
        pending_articulations = []
        pending_ornaments = []
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
            ornament = _ornament_name(name)
            if ornament:
                pending_ornaments.append(ornament)
            else:
                pending_articulations.append(_articulation_name(name))
            continue
        if raw.startswith("$") and raw.endswith("$"):
            for event, source_token in _parse_tuplet_token(token):
                append_event(event, source_token)
            continue

        append_event(_parse_event_token(token), raw)

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
            if key.lower() in {"key", "time"}:
                raise ValueError(
                    f"第 {line_no} 行：旧语法 `{key}=` 已废弃，请使用 `1=C` 和 `4/4`"
                )
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
            # 判断 `数字/数字` 是拍号还是旧时值写法：
            #   - 分子为 1（如 1/2、1/4）几乎总是旧时值（音级+斜杠时值），
            #     且 1 拍记法在简谱中无实际意义，一律按旧时值报错。
            #   - 其余（3/4、6/8 等）在行首或紧跟调号 1=X 后视为合法拍号；
            #     出现在其它位置（前面有音符）则是旧时值，报错。
            # 这样 `1/2 3 4` 里的 `1/2` 会被拒绝，避免被静默当成拍号吞掉丢失音符。
            ts = _time_signature_value(raw_token.strip())
            if ts is not None:
                beats, _beat_type = ts
                if beats == 1:
                    raise ValueError(
                        f"第 {line_no} 行第 {match.start() + 1} 列：旧时值写法 "
                        f"`{raw_token}` 已废弃，请使用 q/s/d 前缀，例如 q1 或 q[1+3]"
                    )
                leading = raw_line[: match.start()]
                leading_without_key = re.sub(r"1\s*=\s*[A-G](?:#|b)?", "", leading)
                leading_without_key = leading_without_key.replace("|:", "").strip()
                if leading_without_key:
                    raise ValueError(
                        f"第 {line_no} 行第 {match.start() + 1} 列：旧时值写法 "
                        f"`{raw_token}` 已废弃，请使用 q/s/d 前缀，例如 q1 或 q[1+3]"
                    )
            tokens.append(_Token(raw_token, line_no, match.start() + 1))
            if not _is_key_or_time_token(raw_token):
                saw_score_tokens = True
    return options, tokens, lyrics


def _is_key_or_time_token(token: str) -> bool:
    return (
        _key_signature_value(token) is not None
        or _time_signature_value(token.strip()) is not None
    )


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
    if len(parts) < 2:
        raise _syntax_error(token, "连音组至少需要两个音符，例如 $123$ 或 $1 2 3$")
    duration = Fraction(1, len(parts))
    group_id = f"{token.line}:{token.column}"
    events: list[tuple[Event, str]] = []
    for index, part in enumerate(parts):
        part_token = _Token(part, token.line, token.column + 1 + body.find(part))
        event = _parse_event_token(part_token)
        event.duration = duration
        event.dotted = 0
        event.tuplet_id = group_id
        event.tuplet_count = len(parts)
        event.tuplet_index = index
        event.tuplet_start = index == 0
        event.tuplet_stop = index == len(parts) - 1
        events.append((event, part))
    return events


def _split_tuplet_body(body: str) -> list[str]:
    if not body:
        return []
    if re.search(r"\s", body):
        return [part for part in body.split() if part]
    parts: list[str] = []
    index = 0
    pattern = re.compile(r"(?:bb|x|n|♮|#|b)?[0-7][',]*[#b]?")
    while index < len(body):
        match = pattern.match(body, index)
        if match is None:
            return [body]
        parts.append(match.group(0))
        index = match.end()
    return parts


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
    if "/" in work:
        raise _syntax_error(
            token,
            f"旧时值写法 `{token.value}` 已废弃，请使用 q/s/d 前缀，例如 q1 或 q[1+3]",
        )
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
    match = re.fullmatch(r"\(\^([l.>rf])\)", raw)
    if match is None:
        if raw.startswith("(^") and raw.endswith(")"):
            return "invalid", ""
        return None
    raw_name = match.group(1)
    ornament = _ornament_name(raw_name)
    if ornament:
        return "ornament", ornament
    return "articulation", _articulation_name(raw_name)


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
