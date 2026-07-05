from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import re

from ..jianpu_tokens import (
    consume_duration_prefix,
    consume_duration_suffix,
    duration_prefix,
    tuplet_duration_unit_count,
)
from ..constants import DYNAMICS, MICROTONAL_TOKEN_TO_ALTER
from ..performance_marks import (
    PERFORMANCE_MARKS,
    event_mark_ids,
    get_performance_mark,
    mark_for_token,
    normalize_event_marks,
)
from ...models.common.types import (
    ACCEPTED_INSTRUMENT_PROFILES,
    SUPPORTED_INSTRUMENT_PROFILES,
    InstrumentProfile,
    normalize_instrument_profile,
)
from ...models.score import (
    Beat,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    TextBlock,
    TupletSpan,
)


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
    accidental: Fraction = Fraction(0, 1)


@dataclass(slots=True)
class _Token:
    value: str
    line: int
    column: int
    start_utf16: int | None = None
    end_utf16: int | None = None


@dataclass(slots=True)
class ParsedJianpuPart:
    score: JianpuScore
    part_index: int
    part_name: str
    body_start_utf16: int
    body_end_utf16: int
    page_index: int = 0
    page_input_file_name: str = ""
    page_start_measure: int | None = None


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


_PART_MARKER_RE = re.compile(
    r"^[ \t]*//[ \t]*@part[ \t]+(?P<number>\d+)[ \t]+"
    r'name=(?P<name>"(?:\\.|[^"\\])*")[ \t]*$',
    re.MULTILINE,
)
_PART_MARKER_START_RE = re.compile(
    r"^[ \t]*//[ \t]*@part\b.*$",
    re.MULTILINE,
)
_PAGE_MARKER_RE = re.compile(
    r"^[ \t]*//[ \t]*@page[ \t]+(?P<number>\d+)[ \t]+"
    r"start=(?P<start>auto|\d+)"
    r"(?:[ \t]+name=(?P<name>.+?))?[ \t]*$",
    re.MULTILINE,
)


@dataclass(slots=True)
class _ParsedPageMarker:
    number: int
    start_measure: int | None
    input_file_name: str
    start: int
    end: int


def _parse_page_marker_name(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                return parsed
        except json.JSONDecodeError:
            return value[1:-1] if value.endswith('"') else value[1:]
        return value
    return value


def _find_page_markers(text: str) -> list[_ParsedPageMarker]:
    markers: list[_ParsedPageMarker] = []
    for match in _PAGE_MARKER_RE.finditer(text):
        number = int(match.group("number"))
        raw_start = match.group("start")
        start_measure: int | None = None
        if raw_start != "auto":
            start_measure = int(raw_start)
        input_file_name = _parse_page_marker_name(match.group("name") or "")
        markers.append(
            _ParsedPageMarker(
                number=number,
                start_measure=start_measure,
                input_file_name=input_file_name,
                start=match.start(),
                end=match.end(),
            )
        )
    return markers


def _strip_page_marker_lines(text: str) -> str:
    return _PAGE_MARKER_RE.sub("", text)


def parse_jianpu_scores(text: str, *, title: str | None = None) -> list[JianpuScore]:
    return [part.score for part in parse_jianpu_parts(text, title=title)]


def parse_jianpu_parts(
    text: str,
    *,
    title: str | None = None,
) -> list[ParsedJianpuPart]:
    text = text.lstrip("\ufeff")
    page_markers = _find_page_markers(text)
    for i, page_marker in enumerate(page_markers):
        if page_marker.number != i + 1:
            raise ValueError(
                f"分页标记序号不连续：期望 @page {i + 1}，实际 @page {page_marker.number}"
            )

    markers = list(_PART_MARKER_RE.finditer(text))
    marker_lines = list(_PART_MARKER_START_RE.finditer(text))
    if len(markers) != len(marker_lines):
        raise ValueError(
            '分谱标记格式无效，请使用 // @part 1 name="声部名称"，'
            '名称中的引号需要写成 \\"'
        )
    if not markers:
        score = parse_jianpu_score(_strip_page_marker_lines(text), title=title)
        if page_markers:
            page = page_markers[0]
            score.page_index = page.number - 1
            score.page_count = len(page_markers)
            score.page_input_file_name = page.input_file_name
            score.page_start_measure = page.start_measure
        return [
            ParsedJianpuPart(
                score=score,
                part_index=0,
                part_name="",
                body_start_utf16=0,
                body_end_utf16=_utf16_length(text),
                page_index=score.page_index,
                page_input_file_name=score.page_input_file_name,
                page_start_measure=score.page_start_measure,
            )
        ]
    prefix = text[: markers[0].start()]
    prefix_without_page_markers = _strip_page_marker_lines(prefix)
    if prefix_without_page_markers.strip():
        raise ValueError("第一个分谱标记之前不能包含简谱正文")

    parts: list[ParsedJianpuPart] = []
    current_page_start: int = -1
    page_part_index = 0
    for i, match in enumerate(markers):
        marker_number = int(match.group("number"))
        preceding_pages = [pm for pm in page_markers if pm.start < match.start()]
        page_start = preceding_pages[-1].start if preceding_pages else -1
        if page_start != current_page_start:
            current_page_start = page_start
            page_part_index = 0
        page_part_index += 1
        if marker_number != page_part_index:
            raise ValueError(
                f"分谱标记序号不连续：期望 @part {page_part_index}，实际 @part {marker_number}"
            )
        try:
            part_name = json.loads(match.group("name"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {i + 1} 个分谱名称不是有效 JSON 字符串") from exc
        if not isinstance(part_name, str):
            raise ValueError(f"第 {i + 1} 个分谱名称必须是字符串")
        start = match.end()
        if text[start : start + 2] == "\r\n":
            start += 2
        elif start < len(text) and text[start] in {"\n", "\r"}:
            start += 1
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        part_text = text[start:end]
        part_text_without_page_markers = _strip_page_marker_lines(part_text)
        score = parse_jianpu_score(part_text_without_page_markers, title=title)
        score.part_index = len(parts)
        score.part_name = part_name
        page_index = 0
        page_input_file_name = ""
        page_start_measure: int | None = None
        if preceding_pages:
            page = preceding_pages[-1]
            page_index = page.number - 1
            page_input_file_name = page.input_file_name
            page_start_measure = page.start_measure
        score.page_index = page_index
        score.page_input_file_name = page_input_file_name
        score.page_start_measure = page_start_measure
        parts.append(
            ParsedJianpuPart(
                score=score,
                part_index=score.part_index,
                part_name=part_name,
                body_start_utf16=_utf16_length(text[:start]),
                body_end_utf16=_utf16_length(text[:end]),
                page_index=page_index,
                page_input_file_name=page_input_file_name,
                page_start_measure=page_start_measure,
            )
        )

    part_count = len(parts)
    page_count = len(page_markers) if page_markers else 1
    for part in parts:
        part.score.part_count = part_count
        part.score.page_count = page_count
    return parts


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def parse_jianpu_score(text: str, *, title: str | None = None) -> JianpuScore:
    normalized = text.lstrip("\ufeff")
    options, token_lines, lyrics = _read_new_syntax(normalized)
    if title and options.title == "简谱":
        options.title = title
    score = JianpuScore(
        title=options.title,
        target_key=options.key,
        source_key=options.key,
        beats=options.beats,
        beat_type=options.beat_type,
        tempo=options.tempo,
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

    def append_event(event: Event, raw: str, token: _Token | None = None) -> None:
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
        if token is not None:
            event.source_start_utf16 = token.start_utf16
            event.source_end_utf16 = token.end_utf16
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
            _set_slide_direction(
                last_pitched_event,
                event,
                instrument_profile=options.instrument_profile,
            )
        if event.slur_start:
            open_slur = True
        if event.slur_stop and open_slur:
            open_slur = False
        # Propagate tie across measures: if a previous note had tie_start,
        # the next note automatically receives tie_stop even without explicit ~
        if open_tie and not event.tie_stop:
            event.tie_stop = True
        if event.tie_start:
            open_tie = True
        elif event.tie_stop:
            open_tie = False
        normalize_event_marks(event)
        _validate_instrument_mark_target(event, options.instrument_profile)
        current_events.append(event)
        cursor += event.duration
        if event.kind == "note":
            last_pitched_event = event

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
            if mark_for_token(name) is None and _ornament_name(name) is None:
                inline_marks, event_part = _consume_tuplet_inline_marks(raw)
                if not inline_marks or not event_part:
                    raise _syntax_error(token, f"不支持的演奏标记：{raw}")
                event_offset = raw.find(event_part)
                event_token = _Token(
                    event_part,
                    token.line,
                    token.column + event_offset,
                )
                event = _parse_event_token(event_token)
                _apply_inline_marks(event, inline_marks)
                append_event(event, raw, token)
                continue
            kind, mark = _mark_kind_name(name)
            if kind == "spanner":
                pending_slide = True
                continue
            if kind == "ornament":
                pending_ornaments.append(mark)
            elif kind == "technical":
                pending_technical.append(mark)
            else:
                pending_articulations.append(mark)
            continue
        if raw.startswith("$") and raw.endswith("$"):
            for event, source_token in _parse_tuplet_token(token):
                append_event(event, source_token, token)
            continue

        append_event(_parse_event_token(token), raw, token)

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
    saw_key = False
    saw_score_tokens = False
    raw_lines = text.splitlines(keepends=True)
    line_start_utf16 = 0
    line_utf16_starts: list[int] = []
    for raw_line_with_ending in raw_lines:
        line_utf16_starts.append(line_start_utf16)
        line_start_utf16 += _utf16_length(raw_line_with_ending)
    for line_no, raw_with_ending in enumerate(raw_lines, start=1):
        original_line = raw_with_ending.rstrip("\r\n")
        raw_line = original_line
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
                if saw_score_tokens or saw_key:
                    column = raw_line.find(stripped)
                    tokens.append(
                        _token_with_offsets(
                            stripped,
                            line_no,
                            column,
                            line_utf16_starts[line_no - 1],
                            original_line,
                        )
                    )
                else:
                    options.key = value
                    saw_key = True
                continue
            if key == "title":
                options.title = value or options.title
                continue
            if key == "tempo":
                options.tempo = int(value)
                continue
            if key == "instrument":
                if value not in ACCEPTED_INSTRUMENT_PROFILES:
                    raise ValueError(
                        f"第 {line_no} 行：不支持的乐器模式 {value}，"
                        "请使用 " + "、".join(SUPPORTED_INSTRUMENT_PROFILES)
                    )
                options.instrument_profile = normalize_instrument_profile(value)
                continue
        if re.fullmatch(r"\d+/\d+", stripped) and not saw_time:
            beats, beat_type = stripped.split("/", 1)
            if saw_score_tokens:
                column = raw_line.find(stripped)
                tokens.append(
                    _token_with_offsets(
                        stripped,
                        line_no,
                        column,
                        line_utf16_starts[line_no - 1],
                        original_line,
                    )
                )
            else:
                options.beats = int(beats)
                options.beat_type = int(beat_type)
                saw_time = True
            continue
        for match in re.finditer(r"\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+", raw_line):
            raw_token = match.group(0)
            if _is_measure_label_token(raw_token):
                continue
            original_column = original_line.find(raw_line)
            if original_column < 0:
                original_column = 0
            tokens.append(
                _token_with_offsets(
                    raw_token,
                    line_no,
                    original_column + match.start(),
                    line_utf16_starts[line_no - 1],
                    original_line,
                )
            )
            if not _is_key_or_time_token(raw_token):
                saw_score_tokens = True
    return options, tokens, lyrics


def _token_with_offsets(
    value: str,
    line: int,
    column: int,
    line_start_utf16: int,
    original_line: str,
) -> _Token:
    return _Token(
        value=value,
        line=line,
        column=max(0, column) + 1,
        start_utf16=_utf16_length(original_line[: max(0, column)]) + line_start_utf16,
        end_utf16=_utf16_length(original_line[: max(0, column) + len(value)])
        + line_start_utf16,
    )


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


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
    match = re.match(r"^\s*(\d+)([.:：])(?P<gap>\s+|$)", line)
    if match is None:
        return line
    if (
        match.group(2) == "."
        and 0 <= int(match.group(1)) <= 7
        and not line[match.end() :].strip()
    ):
        return line
    return line[match.end() :]


def _is_measure_label_token(token: str) -> bool:
    match = re.fullmatch(r"(\d+)([.:：])", token.strip())
    if match is None:
        return False
    return match.group(2) != "." or int(match.group(1)) > 7


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
    explicit_ratio, body = _consume_tuplet_ratio(body, token)
    parts = _split_tuplet_body(body)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    pending_ornaments: list[str] = []
    pending_technical: list[str] = []
    parsed: list[tuple[Event, str]] = []
    for part in parts:
        if part.startswith("^") and _match_mark_token(part[1:]) is None:
            raise _syntax_error(
                token,
                f"不支持的演奏标记：{_leading_mark_token(part)}",
            )
        mark = _tuplet_standalone_mark(part)
        if mark is not None:
            kind, name = mark
            if kind == "dynamic":
                pending_dynamic = name
            elif kind == "ornament":
                _append_unique_mark(pending_ornaments, name)
            elif kind == "technical":
                _append_unique_mark(pending_technical, name)
            elif kind == "spanner":
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
        inline_technical = [name for kind, name in inline_marks if kind == "technical"]
        has_slide = "__slide_from_previous__" in pending_technical or any(
            kind == "spanner" for kind, _name in inline_marks
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
            [mark for mark in pending_technical if mark != "__slide_from_previous__"],
            inline_technical,
        )
        event.slide_stop = has_slide
        normalize_event_marks(event)
        pending_dynamic = None
        pending_articulations = []
        pending_ornaments = []
        pending_technical = []
        parsed.append((event, event_part))
    if not parsed:
        raise _syntax_error(token, "连音组不能为空")
    if len(parsed) < 2 and explicit_ratio is None:
        raise _syntax_error(token, "连音组至少需要两个音符，例如 $123$ 或 $1 2 3$")
    has_explicit_duration = any(
        _has_tuplet_duration_prefix(source_token) for _event, source_token in parsed
    )
    if explicit_ratio is not None:
        actual_count, normal_count = explicit_ratio
    elif has_explicit_duration:
        actual_count = tuplet_duration_unit_count(
            event.duration for event, _source_token in parsed
        )
        normal_count = _tuplet_normal_notes(actual_count)
    else:
        actual_count = len(parsed)
        normal_count = _tuplet_normal_notes(actual_count)
    group_id = f"{token.line}:{token.column}"
    events: list[tuple[Event, str]] = []
    for index, (event, source_token) in enumerate(parsed):
        if explicit_ratio is not None or has_explicit_duration:
            event.duration *= Fraction(normal_count, actual_count)
        else:
            event.duration = Fraction(1, actual_count)
        event.dotted = 0
        event.tuplet_id = group_id
        event.tuplet_count = actual_count
        event.tuplet_normal_count = normal_count
        event.tuplet_index = index
        event.tuplet_start = index == 0
        event.tuplet_stop = index == len(parsed) - 1
        event.tuplet_spans = [
            TupletSpan(
                id=group_id,
                start=event.tuplet_start,
                stop=event.tuplet_stop,
            )
        ]
        events.append((event, source_token))
    return events


def _consume_tuplet_ratio(
    body: str,
    token: _Token,
) -> tuple[tuple[int, int] | None, str]:
    match = re.match(r"^(\d+)\s*:\s*(\d+)\s*;", body)
    if match is None:
        return None, body
    actual_count = int(match.group(1))
    normal_count = int(match.group(2))
    if actual_count <= 0 or normal_count <= 0:
        raise _syntax_error(token, "连音组比例必须是正整数，例如 $3:2;q1 q2$")
    return (actual_count, normal_count), body[match.end() :].strip()


def _has_tuplet_duration_prefix(source_token: str) -> bool:
    work = source_token.strip().lstrip("(~")
    return bool(duration_prefix(work))


def _tuplet_normal_notes(actual_notes: int) -> int:
    normal_notes = 1
    while normal_notes * 2 <= actual_notes:
        normal_notes *= 2
    return max(1, normal_notes)


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
            _COMPACT_TUPLET_EVENT_PATTERN,
            body[index:],
        )
        if match is None or not match.group(0):
            return [body]
        index += match.end()
        parts.append(body[start:index])
    return parts


_COMPACT_PITCH_PATTERN = (
    r"(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?"
    r"[1-7][',]*(?:bb|x|#|b)?"
)
_COMPACT_NOTE_OR_REST_PATTERN = (
    r"(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?"
    r"[0-7][',]*(?:bb|x|#|b)?"
)
_COMPACT_CHORD_PATTERN = (
    rf"\[{_COMPACT_PITCH_PATTERN}"
    rf"(?:\+{_COMPACT_PITCH_PATTERN})+\]"
)
_COMPACT_TUPLET_EVENT_PATTERN = (
    rf"~?\(?(?:[whqs]|d+)?"
    rf"(?:{_COMPACT_CHORD_PATTERN}|{_COMPACT_NOTE_OR_REST_PATTERN})"
    r"\.*-*\)?~?"
)


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


def _apply_inline_marks(
    event: Event,
    marks: list[tuple[str, str]],
) -> None:
    inline_dynamic = next(
        (name for kind, name in reversed(marks) if kind == "dynamic"),
        None,
    )
    if inline_dynamic is not None:
        event.dynamic = inline_dynamic
    event.articulations = _unique_marks(
        list(event.articulations),
        [name for kind, name in marks if kind == "articulation"],
    )
    if event.articulations:
        event.articulation = event.articulations[0]
    event.ornaments = _unique_marks(
        list(event.ornaments),
        [name for kind, name in marks if kind == "ornament"],
    )
    event.technical = _unique_marks(
        list(event.technical),
        [name for kind, name in marks if kind == "technical"],
    )
    event.slide_stop = event.slide_stop or any(
        kind == "spanner" for kind, _name in marks
    )
    normalize_event_marks(event)


def _match_dynamic_prefix(value: str) -> str | None:
    for dynamic in sorted(DYNAMICS, key=len, reverse=True):
        if value.startswith(dynamic):
            return dynamic
    return None


def _parse_event_token(token: _Token) -> Event:
    raw = token.value
    work = raw.strip()
    slur_start = work.startswith("(")
    if slur_start:
        work = work[1:]
    tie_stop = work.startswith("~")
    if tie_stop:
        work = work[1:]
    tie_start = work.endswith("~")
    if tie_start:
        work = work[:-1]
    slur_stop = work.endswith(")")
    if slur_stop:
        work = work[:-1]
    has_duration_prefix = bool(duration_prefix(work))
    duration, work = _consume_duration_prefix(work)
    if has_duration_prefix and work.startswith("."):
        raise _syntax_error(
            token,
            f"时值前缀后的附点 `{token.value}` 非法，附点必须写在音级之后，例如 h4'. 而不是 h.4'",
        )
    duration, work, dotted = consume_duration_suffix(duration, work)
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
    event.dotted = dotted
    event.tie_start = tie_start
    event.tie_stop = tie_stop
    event.slur_start = slur_start
    event.slur_stop = slur_stop
    return event


def _parse_pitch(raw: str, token: _Token) -> JianpuPitch:
    accidental = Fraction(0, 1)
    accidental_text: str | None = None
    value = raw
    microtonal_prefix = next(
        (prefix for prefix in ("tqf", "tqs", "qf", "qs") if value.startswith(prefix)),
        None,
    )
    if microtonal_prefix is not None:
        accidental = MICROTONAL_TOKEN_TO_ALTER[microtonal_prefix]
        accidental_text = microtonal_prefix
        value = value[len(microtonal_prefix) :]
    elif value.startswith("bb"):
        accidental = Fraction(-2, 1)
        accidental_text = "bb"
        value = value[2:]
    elif value.startswith("x"):
        accidental = Fraction(2, 1)
        accidental_text = "x"
        value = value[1:]
    elif value.startswith(("n", "♮")):
        accidental = Fraction(0, 1)
        accidental_text = "♮"
        value = value[1:]
    elif value.startswith("#"):
        accidental = Fraction(1, 1)
        accidental_text = "#"
        value = value[1:]
    elif value.startswith("b"):
        accidental = Fraction(-1, 1)
        accidental_text = "b"
        value = value[1:]
    if value.endswith("bb"):
        accidental = Fraction(-2, 1)
        accidental_text = "bb"
        value = value[:-2]
    elif value.endswith("x"):
        accidental = Fraction(2, 1)
        accidental_text = "x"
        value = value[:-1]
    elif value.endswith("#"):
        accidental = Fraction(1, 1)
        accidental_text = "#"
        value = value[:-1]
    elif value.endswith("b"):
        accidental = Fraction(-1, 1)
        accidental_text = "b"
        value = value[:-1]
    octave = value.count("'") - value.count(",")
    value = value.replace("'", "").replace(",", "")
    if value not in {"1", "2", "3", "4", "5", "6", "7"}:
        raise _syntax_error(
            token,
            f"不支持的简谱 token：{token.value}，请使用 1-7、0、#1、qs1、"
            "q1、[1+3+5] 等新语法",
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
    actual = measure.span_duration
    if actual < target:
        measure.validation_errors.append(f"小节少拍：实际 {actual}，目标 {target}")
    elif actual > target:
        measure.validation_errors.append(f"小节超拍：实际 {actual}，目标 {target}")


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


def _leading_mark_token(value: str) -> str:
    match = re.match(r"\^[A-Za-z0-9.>\-]+", value)
    return match.group(0) if match is not None else value


_MARK_TOKENS = tuple(
    sorted(
        {mark.token for mark in PERFORMANCE_MARKS},
        key=len,
        reverse=True,
    )
)


def _set_slide_direction(
    start: Event,
    stop: Event,
    *,
    instrument_profile: InstrumentProfile,
) -> None:
    if len(start.pitches) != 1 or len(stop.pitches) != 1:
        if instrument_profile == "guzheng":
            raise ValueError("古筝有时值滑音 ^lh 只能连接两个单音，不能连接和弦")
        return
    start_rank = start.pitches[0].rank
    stop_rank = stop.pitches[0].rank
    if start_rank == stop_rank:
        if instrument_profile == "guzheng":
            raise ValueError("古筝有时值滑音 ^lh 的起止音高不能相同")
        return
    direction = "up" if stop_rank > start_rank else "down"
    start.slide_direction = direction
    stop.slide_direction = direction


def _validate_instrument_mark_target(
    event: Event,
    instrument_profile: InstrumentProfile,
) -> None:
    if instrument_profile not in {"guzheng", "ruan"}:
        return
    mark_ids = event_mark_ids(
        list(event.articulations),
        list(event.ornaments),
        list(event.technical),
    )
    for mark_id in mark_ids:
        mark = get_performance_mark(mark_id)
        if mark is None or not any(
            profile == instrument_profile for profile, _label in mark.labels
        ):
            continue
        label = mark.label_for(instrument_profile)
        if event.kind != "note":
            raise ValueError(f"{label}演奏标记 ^{mark.token} 后必须跟随音符")
        if mark.target == "chord" and not event.is_chord:
            raise ValueError(
                f"演奏标记 ^{mark.token}（{label}）后必须跟随和弦，例如 [3+5]"
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
