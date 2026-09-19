from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from fractions import Fraction

from ...models.common.errors import JianpuValidationError
from ...models.common.types import (
    ACCEPTED_INSTRUMENT_PROFILES,
    SUPPORTED_INSTRUMENT_PROFILES,
    InstrumentProfile,
    normalize_instrument_profile,
)
from ...models.score import (
    Beat,
    DEFAULT_TEMPO,
    Event,
    JianpuPitch,
    JianpuScore,
    Measure,
    SlideDirection,
    TextBlock,
    TupletSpan,
)
from ...models.syntax.schemas import SyntaxDiagnostic, SyntaxSeverity
from ..constants import DYNAMICS, MICROTONAL_TOKEN_TO_ALTER
from ..jianpu_tokens import (
    consume_duration_prefix,
    consume_duration_suffix,
    duration_prefix,
    tuplet_normal_notes,
)
from ..measure_counts import find_measure_count_mismatch
from ..performance_marks import (
    PERFORMANCE_MARKS,
    event_mark_ids,
    get_performance_mark,
    mark_for_token,
    normalize_event_marks,
)
from ..pitch_spelling import jianpu_pitch_to_written

MIN_TEMPO = 20
MAX_TEMPO = 300


@dataclass(slots=True)
class JianpuOptions:
    key: str = "C"
    beats: int = 4
    beat_type: int = 4
    title: str | None = None
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
    measure: str | None = None
    standalone_line: bool = False


class JianpuSyntaxError(JianpuValidationError):
    """A syntax error that retains the source token used to produce it."""

    error_code = "jianpu_syntax"

    def __init__(
        self,
        token: _Token,
        message: str,
        *,
        severity: SyntaxSeverity = "error",
    ) -> None:
        self.token = token
        self.severity: SyntaxSeverity = severity
        self.detail = message
        super().__init__(f"第 {token.line} 行第 {token.column} 列：{message}")

    def diagnostic(self) -> SyntaxDiagnostic:
        start = self.token.start_utf16 if self.token.start_utf16 is not None else 0
        end = self.token.end_utf16 if self.token.end_utf16 is not None else start
        return SyntaxDiagnostic(
            id=f"syntax-error-{self.token.line}-{self.token.column}-{start}-{end}",
            message=self.detail,
            line=self.token.line,
            column=self.token.column,
            start=start,
            end=end,
            severity=self.severity,
            measure=self.token.measure,
        )


@dataclass(slots=True)
class ParsedJianpuPart:
    score: JianpuScore
    part_index: int
    part_name: str
    body_start_utf16: int
    body_end_utf16: int
    page_index: int = 0
    page_input_file_name: str = ""
    measure_number_base: int = 1


def parse_jianpu(text: str) -> tuple[JianpuOptions, list[ParsedToken]]:
    score = parse_jianpu_score(text)
    options = JianpuOptions(
        key=score.target_key,
        beats=score.beats,
        beat_type=score.beat_type,
        title=score.title,
        tempo=score.tempo,
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
    r'name=(?P<name>"(?:\\.|[^"\\])*")[ \t]*\r?$',
    re.MULTILINE,
)
_PART_MARKER_START_RE = re.compile(
    r"^[ \t]*//[ \t]*@part\b.*$",
    re.MULTILINE,
)
_PAGE_MARKER_RE = re.compile(
    r"^[ \t]*//[ \t]*@page[ \t]+(?P<number>\d+)"
    r"(?:[ \t]+name=(?P<name>\"(?:\\.|[^\"\\])*\"))?[ \t]*\r?$",
    re.MULTILINE,
)
_PAGE_MARKER_START_RE = re.compile(
    r"^[ \t]*//[ \t]*@page\b.*$",
    re.MULTILINE,
)


@dataclass(slots=True)
class _ParsedPageMarker:
    number: int
    input_file_name: str
    start: int
    end: int


def _marker_token(text: str, start: int, end: int) -> _Token:
    line = text.count("\n", 0, start) + 1
    line_start = text.rfind("\n", 0, start) + 1
    return _Token(
        value=text[start:end],
        line=line,
        column=start - line_start + 1,
        start_utf16=_utf16_length(text[:start]),
        end_utf16=_utf16_length(text[:end]),
    )


def _find_page_markers(text: str) -> list[_ParsedPageMarker]:
    markers: list[_ParsedPageMarker] = []
    for match in _PAGE_MARKER_RE.finditer(text):
        number = int(match.group("number"))
        raw_name = match.group("name")
        input_file_name = ""
        if raw_name:
            try:
                parsed_name = json.loads(raw_name)
            except json.JSONDecodeError as exc:
                raise JianpuSyntaxError(
                    _marker_token(text, match.start(), match.end()),
                    "分页标记名称不是有效 JSON 字符串",
                ) from exc
            if not isinstance(parsed_name, str):
                raise JianpuSyntaxError(
                    _marker_token(text, match.start(), match.end()),
                    "分页标记名称必须是字符串",
                )
            input_file_name = parsed_name
        markers.append(
            _ParsedPageMarker(
                number=number,
                input_file_name=input_file_name,
                start=match.start(),
                end=match.end(),
            )
        )
    return markers


def _strip_page_marker_lines(text: str) -> str:
    # Blank marker content instead of deleting it so line numbers and UTF-16
    # offsets in the remaining text stay aligned with the original document.
    return _PAGE_MARKER_RE.sub(lambda match: " " * _utf16_length(match.group(0)), text)


def parse_jianpu_scores(text: str, *, title: str | None = None) -> list[JianpuScore]:
    return [part.score for part in parse_jianpu_parts(text, title=title)]


def validate_jianpu_text(
    text: str,
    *,
    check_measure_durations: bool = False,
) -> list[SyntaxDiagnostic]:
    """Validate token syntax while preserving strict export parsing."""
    normalized = text.lstrip("\ufeff")
    diagnostics: list[SyntaxDiagnostic] = []
    try:
        _validate_marker_structure(normalized)
        _options, token_lines, _lyrics = _read_new_syntax(normalized)
        _relabel_measure_numbers(
            token_lines, _measure_number_spans(normalized, token_lines)
        )
    except JianpuSyntaxError as exc:
        diagnostics.append(exc.diagnostic())
        token_lines = []
    except ValueError as exc:
        diagnostics.append(_document_syntax_diagnostic(normalized, str(exc)))
        token_lines = []
    for token in token_lines:
        try:
            _validate_jianpu_token(token)
        except JianpuSyntaxError as exc:
            diagnostics.append(exc.diagnostic())
            if _is_structural_syntax_error(exc):
                break
    if diagnostics and not check_measure_durations:
        return diagnostics
    duration_text = (
        _mask_diagnostic_ranges(normalized, diagnostics) if diagnostics else normalized
    )
    has_markers = _PART_MARKER_START_RE.search(
        normalized
    ) or _PAGE_MARKER_START_RE.search(normalized)
    duration_parts: list[ParsedJianpuPart] = []
    for _attempt in range(100):
        try:
            if has_markers:
                duration_parts = parse_jianpu_parts(duration_text)
            else:
                score = parse_jianpu_score(duration_text)
                duration_parts = [
                    ParsedJianpuPart(
                        score=score,
                        part_index=0,
                        part_name="",
                        body_start_utf16=0,
                        body_end_utf16=_utf16_length(normalized),
                    )
                ]
        except JianpuSyntaxError as exc:
            diagnostic = exc.diagnostic()
        except ValueError as exc:
            diagnostic = _document_syntax_diagnostic(normalized, str(exc))
        except Exception as exc:  # noqa: BLE001 — 兜底，防止内部错误逃逸成 HTTP 500
            if diagnostics:
                return diagnostics
            return [
                _document_syntax_diagnostic(
                    normalized, f"内部解析错误（{type(exc).__name__}）：{exc}"
                )
            ]
        else:
            break

        if not check_measure_durations:
            return [diagnostic]
        if diagnostic.end <= diagnostic.start or any(
            item.id == diagnostic.id for item in diagnostics
        ):
            return diagnostics or [diagnostic]
        diagnostics.append(diagnostic)
        masked = _mask_diagnostic_ranges(normalized, diagnostics)
        if masked == duration_text:
            return diagnostics
        duration_text = masked
    else:
        return diagnostics

    _assign_measure_number_bases(duration_parts)

    if has_markers:
        try:
            _validate_part_measure_counts(duration_text, duration_parts)
        except JianpuSyntaxError as exc:
            diagnostic = exc.diagnostic()
            if not check_measure_durations:
                return [diagnostic]
            if not any(item.id == diagnostic.id for item in diagnostics):
                diagnostics.append(diagnostic)
    if check_measure_durations:
        diagnostics.extend(
            _measure_duration_diagnostics(
                normalized,
                duration_parts,
                excluded_ranges=[(item.start, item.end) for item in diagnostics],
            )
        )
    return diagnostics


def _measure_number_spans(
    text: str,
    tokens: list[_Token] | None = None,
) -> list[tuple[int, int, int]]:
    """各声部段的 (start_utf16, end_utf16, 连续起始小节号)。

    优先用 `parse_jianpu_parts` 的准确小节数；解析失败时（文档本身有语法错误，
    而这正是最需要正确小节号的场景）退化为按标记分段 + token 小节线估算。
    无标记文档返回空列表，`_relabel_measure_numbers` 会原样保留累计号。
    """
    if not (_PART_MARKER_START_RE.search(text) or _PAGE_MARKER_START_RE.search(text)):
        return []
    bounds = _part_bounds_from_markers(text)
    if not bounds:
        return []
    try:
        parts = parse_jianpu_parts(text)
    except Exception:  # noqa: BLE001 — 与 validate 第 2 轮解析的兜底对齐
        parts = []
    if len(parts) == len(bounds):
        _assign_measure_number_bases(parts)
        return [
            (part.body_start_utf16, part.body_end_utf16, part.measure_number_base)
            for part in parts
        ]
    return _estimate_measure_spans(text, bounds, tokens or [])


def _part_bounds_from_markers(text: str) -> list[tuple[int, int, bool]]:
    """从标记位置算出各声部的正文区间：代码点 (start, end, 是否本页第一个声部)。

    不依赖解析成功；切分规则与 `parse_jianpu_parts`（含 F2 的 @page 切断与页眉前移）一致。
    """
    page_markers = _find_page_markers(text)
    markers = list(_PART_MARKER_RE.finditer(text))
    bounds: list[tuple[int, int, bool]] = []
    current_page_start = -1
    pending_header_start: int | None = None
    for index, match in enumerate(markers):
        preceding_pages = [pm for pm in page_markers if pm.start < match.start()]
        page_start = preceding_pages[-1].start if preceding_pages else -1
        is_page_first = page_start != current_page_start
        current_page_start = page_start
        start = match.end()
        if text[start : start + 2] == "\r\n":
            start += 2
        elif start < len(text) and text[start] in {"\n", "\r"}:
            start += 1
        if pending_header_start is not None:
            start = min(start, pending_header_start)
            pending_header_start = None
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        next_page_start = next(
            (pm.start for pm in page_markers if start < pm.start < end),
            None,
        )
        if next_page_start is not None:
            end = next_page_start
            header_newline = text.find("\n", next_page_start)
            pending_header_start = (
                len(text) if header_newline < 0 else header_newline + 1
            )
        bounds.append((start, end, is_page_first))
    return bounds


def _estimate_measure_spans(
    text: str,
    bounds: list[tuple[int, int, bool]],
    tokens: list[_Token],
) -> list[tuple[int, int, int]]:
    """解析失败时估算各声部段的连续起始号。

    整篇 `parse_jianpu_parts` 失败通常只因**某一段**有语法错误，所以这里逐段单独
    `parse_jianpu_score`：好的段能拿到准确的 `sum(repeat_count)`（含反复结构），
    只有真正坏掉的那段才回退到 token 累计号极差。这样坏段之前的页完全准确，
    R7 的偏差被限制在坏段所在的页。与准确路径一样按页取最大值推进。
    """
    measure_by_offset = [
        (token.start_utf16, int(token.measure))
        for token in tokens
        if token.start_utf16 is not None and token.measure
    ]
    spans: list[tuple[int, int, int]] = []
    cursor = 1
    page_counts: list[int] = []
    for start_cp, end_cp, is_page_first in bounds:
        start_utf16 = _utf16_length(text[:start_cp])
        end_utf16 = _utf16_length(text[:end_cp])
        if is_page_first and page_counts:
            cursor += max(page_counts)
            page_counts = []
        segment = _strip_page_marker_lines(text[start_cp:end_cp])
        try:
            segment_score = parse_jianpu_score(segment)
            count = sum(m.repeat_count for m in segment_score.measures)
        except Exception:  # noqa: BLE001 — 坏段回退到累计号极差
            inside = [
                value
                for offset, value in measure_by_offset
                if start_utf16 <= offset < end_utf16
            ]
            count = max(inside) - min(inside) + 1 if inside else 0
        spans.append((start_utf16, end_utf16, cursor))
        page_counts.append(count)
    return spans


def _relabel_measure_numbers(
    tokens: list[_Token],
    spans: list[tuple[int, int, int]],
) -> None:
    """把 token 的整篇累计小节号改写为按页连续的显示号（原地修改）。"""
    if not spans:
        return
    for start, end, base in spans:
        inside = [
            token
            for token in tokens
            if token.start_utf16 is not None
            and token.measure
            and start <= token.start_utf16 < end
        ]
        if not inside:
            continue
        first = min(int(token.measure) for token in inside)
        for token in inside:
            token.measure = str(base + int(token.measure) - first)


def _mask_diagnostic_ranges(
    text: str,
    diagnostics: list[SyntaxDiagnostic],
) -> str:
    characters = list(text)
    for diagnostic in diagnostics:
        if diagnostic.end <= diagnostic.start:
            continue
        start = _utf16_offset_to_codepoint_index(text, diagnostic.start)
        end = _utf16_offset_to_codepoint_index(text, diagnostic.end)
        for index in range(start, min(end, len(characters))):
            if characters[index] not in {"\n", "\r"}:
                characters[index] = " " * _utf16_length(characters[index])
    return "".join(characters)


def _utf16_offset_to_codepoint_index(text: str, offset: int) -> int:
    consumed = 0
    for index, character in enumerate(text):
        if consumed >= offset:
            return index
        consumed += _utf16_length(character)
    return len(text)


def _assign_measure_number_bases(
    parts: list[ParsedJianpuPart],
    *,
    initial_measure_number: int = 1,
) -> None:
    """为每个 part 写入整篇文档内的连续起始小节号（F3）。

    规则与渲染路径 `exec/render/actions.py:_render_batch_multi_part`
    及前端 `jianpuPageSections.ts:walkJianpuMeasures` 完全一致：
    按页推进，每页取该页各声部「小节数（含 repeat_count）」的最大值累加，
    页内所有声部共用同一个起始号。
    """
    cursor = initial_measure_number
    for _page_index, group in _iter_page_part_groups(parts):
        span = max(
            (
                sum(measure.repeat_count for measure in part.score.measures)
                for part in group
            ),
            default=0,
        )
        for part in group:
            part.measure_number_base = cursor
        cursor += span


def _measure_duration_diagnostics(
    text: str,
    parts: list[ParsedJianpuPart],
    *,
    excluded_ranges: list[tuple[int, int]] | None = None,
) -> list[SyntaxDiagnostic]:
    diagnostics: list[SyntaxDiagnostic] = []
    excluded_ranges = excluded_ranges or []
    for part in parts:
        measure_scope_start: int | None = None
        for measure_index, measure in enumerate(part.score.measures, start=1):
            measure_scope_end = measure.source_end_utf16
            for error in measure.validation_errors:
                start = measure.source_start_utf16
                end = measure_scope_end
                if start is None or end is None:
                    continue
                scope_start = (
                    measure_scope_start
                    if measure_scope_start is not None
                    else _line_start_utf16_offset(text, start)
                )
                if any(
                    scope_start < excluded_end and end > excluded_start
                    for excluded_start, excluded_end in excluded_ranges
                ):
                    continue
                line, column = _line_column_from_utf16_offset(text, start)
                measure_number = (
                    part.measure_number_base
                    + (measure.display_number or measure_index)
                    - 1
                )
                message = _format_measure_duration_warning(error)
                diagnostics.append(
                    SyntaxDiagnostic(
                        id=(
                            "syntax-warning-measure-duration-"
                            f"{part.part_index}-{measure_index}-{start}-{end}"
                        ),
                        message=message,
                        line=line,
                        column=column,
                        start=start,
                        end=end,
                        severity="warning",
                        measure=str(measure_number),
                    )
                )
            if measure_scope_end is not None:
                measure_scope_start = measure_scope_end
    return diagnostics


def _line_start_utf16_offset(text: str, offset: int) -> int:
    codepoint_index = _utf16_offset_to_codepoint_index(text, offset)
    line_start = text.rfind("\n", 0, codepoint_index) + 1
    return _utf16_length(text[:line_start])


def _format_measure_duration_warning(error: str) -> str:
    match = re.fullmatch(r"小节(少拍|超拍)：实际 (.+)，目标 (.+)", error)
    if match is None:
        return error
    kind, actual, target = match.groups()
    return f"{kind}：实际 {actual} 拍，目标 {target} 拍"


def _line_column_from_utf16_offset(text: str, offset: int) -> tuple[int, int]:
    consumed = 0
    line = 1
    line_start = 0
    for index, character in enumerate(text):
        if consumed >= offset:
            break
        if character == "\n":
            line += 1
            line_start = index + 1
        consumed += _utf16_length(character)
    codepoint_offset = 0
    for character in text[:line_start]:
        codepoint_offset += _utf16_length(character)
    column = 1
    consumed = codepoint_offset
    for character in text[line_start:]:
        if consumed >= offset:
            break
        column += 1
        consumed += _utf16_length(character)
    return line, column


def _iter_page_part_groups(
    parts: list[ParsedJianpuPart],
) -> Iterator[tuple[int, list[ParsedJianpuPart]]]:
    """把连续的 part 按 page_index 分组，产出 (page_index, group)。

    多页文档里每一页的声部都是独立编号的（`parse_jianpu_parts` 对每页每声部
    各产出一个 ParsedJianpuPart，各自从 1 开始），因此任何跨页的比较都没有意义。
    F1（小节数一致性）与 F3（连续小节号）共用这份分组语义。
    """
    index = 0
    while index < len(parts):
        page_index = parts[index].page_index
        end = index
        while end < len(parts) and parts[end].page_index == page_index:
            end += 1
        yield page_index, parts[index:end]
        index = end


def _part_marker_token(text: str, part_index: int) -> _Token:
    """第 `part_index` 个 `@part` 标记对应的 token（parts 与标记同序）。"""
    markers = list(_PART_MARKER_RE.finditer(text))
    if part_index >= len(markers):
        return _Token(value="", line=1, column=1, start_utf16=0, end_utf16=0)
    match = markers[part_index]
    return _marker_token(text, match.start(), match.end())


def _validate_part_measure_counts(text: str, parts: list[ParsedJianpuPart]) -> None:
    mismatch = find_measure_count_mismatch([part.score for part in parts])
    if mismatch is None:
        return
    page_index, message = mismatch
    anchor_part = next(
        (part for part in parts if part.page_index == page_index),
        parts[0],
    )
    raise JianpuSyntaxError(
        _part_marker_token(text, anchor_part.part_index),
        message,
        severity="warning",
    )


def _validate_marker_structure(text: str) -> None:
    page_markers = _find_page_markers(text)
    if len(page_markers) != len(list(_PAGE_MARKER_START_RE.finditer(text))):
        offending = _first_invalid_marker_line(
            text, _PAGE_MARKER_RE, _PAGE_MARKER_START_RE
        )
        raise JianpuSyntaxError(
            offending,
            '分页标记格式无效，请使用 // @page 1 或 // @page 1 name="文件名"',
        )
    for index, marker in enumerate(page_markers, start=1):
        if marker.number != index:
            raise JianpuSyntaxError(
                _marker_token(text, marker.start, marker.end),
                f"分页标记序号不连续：期望 @page {index}，实际 @page {marker.number}",
            )
    part_markers = list(_PART_MARKER_RE.finditer(text))
    if len(part_markers) != len(list(_PART_MARKER_START_RE.finditer(text))):
        offending = _first_invalid_marker_line(
            text, _PART_MARKER_RE, _PART_MARKER_START_RE
        )
        raise JianpuSyntaxError(
            offending,
            '分谱标记格式无效，请使用 // @part 1 name="声部名称"',
        )
    for index, match in enumerate(part_markers, start=1):
        try:
            parsed_name = json.loads(match.group("name"))
        except json.JSONDecodeError as exc:
            raise JianpuSyntaxError(
                _marker_token(text, match.start(), match.end()),
                f"第 {index} 个分谱名称不是有效 JSON 字符串",
            ) from exc
        if not isinstance(parsed_name, str):
            raise JianpuSyntaxError(
                _marker_token(text, match.start(), match.end()),
                f"第 {index} 个分谱名称必须是字符串",
            )


def _first_invalid_marker_line(
    text: str,
    full_re: re.Pattern[str],
    start_re: re.Pattern[str],
) -> _Token:
    full_starts = {match.start() for match in full_re.finditer(text)}
    for match in start_re.finditer(text):
        if match.start() not in full_starts:
            return _marker_token(text, match.start(), match.end())
    return _marker_token(text, 0, 0)


def _document_syntax_diagnostic(text: str, raw_message: str) -> SyntaxDiagnostic:
    match = re.match(r"第 (\d+) 行(?:第 (\d+) 列)?[：:]?(.*)", raw_message)
    line = int(match.group(1)) if match else 1
    column = int(match.group(2)) if match and match.group(2) else 1
    message = match.group(3).strip() if match and match.group(3) else raw_message
    lines = text.splitlines(keepends=True)
    start = _utf16_length("".join(lines[: max(0, line - 1)]))
    content = lines[line - 1].rstrip("\r\n") if 0 < line <= len(lines) else ""
    end = start + _utf16_length(content)
    return SyntaxDiagnostic(
        id=f"syntax-error-{line}-{column}-{start}-{end}",
        message=message,
        line=line,
        column=column,
        start=start,
        end=end,
    )


def _validate_jianpu_token(token: _Token) -> None:
    raw = token.value
    measure_mark = _measure_level_mark(raw)
    if (
        raw in {"|", "||", "|:", ":|", "&"}
        or re.fullmatch(r"\*\d+", raw)
        or _key_signature_value(raw) is not None
        or _time_signature_value(raw) is not None
        or (measure_mark is not None and measure_mark[1] is not None)
    ):
        return
    if re.fullmatch(r"\d+/\d+", raw):
        raise _syntax_error(token, f"拍号无效：{raw}，分子分母必须为正整数")
    if _is_tempo_token(raw):
        _parse_tempo_token(token)
        return
    if measure_mark is not None:
        raise _syntax_error(
            token,
            f"不支持的小节级演奏标记：{raw}。请使用 (^l)、(^.)、(^>)、(^r)、(^f)",
        )
    if raw.startswith("\\"):
        if _match_dynamic_prefix(raw[1:]) is None:
            raise _syntax_error(
                token, f"不支持的力度标记：{raw}，请使用 \\p、\\mp、\\f、\\ff 等"
            )
        return
    if raw.startswith("^"):
        name = raw[1:]
        if mark_for_token(name) is not None or _ornament_name(name) is not None:
            return
        inline_marks, event_part = _consume_tuplet_inline_marks(raw)
        if not inline_marks or not event_part:
            raise _syntax_error(token, f"不支持的演奏标记：{raw}")
        event_offset = raw.find(event_part)
        _parse_event_token(
            _Token(
                value=event_part,
                line=token.line,
                column=token.column + event_offset,
                start_utf16=(token.start_utf16 or 0)
                + _utf16_length(raw[:event_offset]),
                end_utf16=token.end_utf16,
                measure=token.measure,
            )
        )
        return
    if _is_tuplet_token(raw):
        _parse_tuplet_token(token)
        return
    if raw.startswith(("$", "($")):
        raise _syntax_error(token, "连音组缺少结束标记 $")
    _parse_event_token(token)


def _is_structural_syntax_error(error: JianpuSyntaxError) -> bool:
    return any(marker in error.detail for marker in ("连音组", "和弦", "缺少结束标记"))


_CONFIG_ONLY_LINE = re.compile(
    r"^(?:1\s*=\s*[A-Ga-g](?:bb|[#b])?"
    r"|\d+\s*/\s*\d+"
    r"|(?:title|tempo|instrument|key|time)\s*=\s*\S.*)$"
)


def _is_config_line(stripped: str) -> bool:
    """配置行不产生小节，允许出现在分谱标记之前 / 分页标记之后（页眉位置）。

    覆盖调号 `1=C`、拍号 `4/4`、以及 `title=` / `tempo=` / `instrument=`
    与已废弃的 `key=` / `time=`。注释行与空行同样视为非正文。
    """
    if not stripped or stripped.startswith("//"):
        return True
    return bool(_CONFIG_ONLY_LINE.match(stripped))


def parse_jianpu_parts(
    text: str,
    *,
    title: str | None = None,
) -> list[ParsedJianpuPart]:
    text = text.lstrip("\ufeff")
    page_markers = _find_page_markers(text)
    page_marker_lines = list(_PAGE_MARKER_START_RE.finditer(text))
    if len(page_markers) != len(page_marker_lines):
        raise JianpuSyntaxError(
            _first_invalid_marker_line(text, _PAGE_MARKER_RE, _PAGE_MARKER_START_RE),
            '分页标记格式无效，请使用 // @page 1 或 // @page 1 name="文件名"，'
            '名称中的引号需要写成 \\"',
        )
    for i, page_marker in enumerate(page_markers):
        if page_marker.number != i + 1:
            raise JianpuSyntaxError(
                _marker_token(text, page_marker.start, page_marker.end),
                f"分页标记序号不连续：期望 @page {i + 1}，实际 @page {page_marker.number}",
            )

    markers = list(_PART_MARKER_RE.finditer(text))
    marker_lines = list(_PART_MARKER_START_RE.finditer(text))
    if len(markers) != len(marker_lines):
        raise JianpuSyntaxError(
            _first_invalid_marker_line(text, _PART_MARKER_RE, _PART_MARKER_START_RE),
            '分谱标记格式无效，请使用 // @part 1 name="声部名称"，'
            '名称中的引号需要写成 \\"',
        )
    if not markers:
        score = parse_jianpu_score(_strip_page_marker_lines(text), title=title)
        if page_markers:
            page = page_markers[0]
            score.page_index = page.number - 1
            score.page_count = len(page_markers)
            score.page_input_file_name = page.input_file_name
        return [
            ParsedJianpuPart(
                score=score,
                part_index=0,
                part_name="",
                body_start_utf16=0,
                body_end_utf16=_utf16_length(text),
                page_index=score.page_index,
                page_input_file_name=score.page_input_file_name,
            )
        ]
    prefix = text[: markers[0].start()]
    prefix_without_page_markers = _strip_page_marker_lines(prefix)
    if any(
        not _is_config_line(line.strip())
        for line in prefix_without_page_markers.splitlines()
    ):
        raise JianpuSyntaxError(
            _marker_token(text, markers[0].start(), markers[0].end()),
            "第一个分谱标记之前不能包含简谱正文",
        )

    # F6：用了 @part 的文档里，每一页都必须有自己的 @part，否则该页正文会被
    # 静默并入上一页最后一个声部、page_index 丢失。完全无 @part 的多页文档
    # （单声部）走上面的「整篇一个 score」分支，不受影响。
    for pm_index, page_marker in enumerate(page_markers):
        next_page_start = (
            page_markers[pm_index + 1].start
            if pm_index + 1 < len(page_markers)
            else len(text)
        )
        if not any(page_marker.end <= m.start() < next_page_start for m in markers):
            raise JianpuSyntaxError(
                _marker_token(text, page_marker.start, page_marker.end),
                f"第 {page_marker.number} 页缺少分谱标记，请在该页 // @page 之后添加 "
                f'// @part 1 name="声部名称"',
            )

    parts: list[ParsedJianpuPart] = []
    current_page_start: int = -1
    page_part_index = 0
    # F2：上一个声部正文被 @page 截断时，其后的页眉归属下一个声部（起点前移）。
    # 最后一个声部之后的页眉 v1 暂静默丢弃，F6（v2）改为显式报错。
    pending_header_start: int | None = None
    for i, match in enumerate(markers):
        marker_number = int(match.group("number"))
        preceding_pages = [pm for pm in page_markers if pm.start < match.start()]
        page_start = preceding_pages[-1].start if preceding_pages else -1
        if page_start != current_page_start:
            current_page_start = page_start
            page_part_index = 0
        page_part_index += 1
        if marker_number != page_part_index:
            raise JianpuSyntaxError(
                _marker_token(text, match.start(), match.end()),
                f"分谱标记序号不连续：期望 @part {page_part_index}，实际 @part {marker_number}",
            )
        try:
            part_name = json.loads(match.group("name"))
        except json.JSONDecodeError as exc:
            raise JianpuSyntaxError(
                _marker_token(text, match.start(), match.end()),
                f"第 {i + 1} 个分谱名称不是有效 JSON 字符串",
            ) from exc
        if not isinstance(part_name, str):
            raise JianpuSyntaxError(
                _marker_token(text, match.start(), match.end()),
                f"第 {i + 1} 个分谱名称必须是字符串",
            )
        start = match.end()
        if text[start : start + 2] == "\r\n":
            start += 2
        elif start < len(text) and text[start] in {"\n", "\r"}:
            start += 1
        # F2：声部正文不得越过下一个 @page 标记——页眉（写在 @page 之后、
        # 本页第一个 @part 之前的调号/拍号等）归属下一页的第一个声部。
        # 实现方式是把下一声部的正文起点前移到页眉起点，而非拼接字符串，
        # 这样 UTF-16 偏移与行号靠 _strip_page_marker_lines 的等长替换自动对齐。
        if pending_header_start is not None:
            start = min(start, pending_header_start)
            pending_header_start = None
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        next_page_start = next(
            (pm.start for pm in page_markers if start < pm.start < end),
            None,
        )
        if next_page_start is not None:
            end = next_page_start
            header_start = next_page_start
            header_newline = text.find("\n", header_start)
            pending_header_start = (
                len(text) if header_newline < 0 else header_newline + 1
            )
        part_text = text[start:end]
        part_text_without_page_markers = _strip_page_marker_lines(part_text)
        try:
            score = parse_jianpu_score(
                part_text_without_page_markers,
                title=title,
            )
        except JianpuSyntaxError as exc:
            raise _remap_part_syntax_error(exc, text, start) from exc
        base_utf16 = _utf16_length(text[:start])
        for measure in score.measures:
            if measure.source_start_utf16 is not None:
                measure.source_start_utf16 += base_utf16
            if measure.source_end_utf16 is not None:
                measure.source_end_utf16 += base_utf16
        score.part_index = len(parts)
        score.part_name = part_name
        page_index = 0
        page_input_file_name = ""
        if preceding_pages:
            page = preceding_pages[-1]
            page_index = page.number - 1
            page_input_file_name = page.input_file_name
        score.page_index = page_index
        score.page_input_file_name = page_input_file_name
        parts.append(
            ParsedJianpuPart(
                score=score,
                part_index=score.part_index,
                part_name=part_name,
                body_start_utf16=_utf16_length(text[:start]),
                body_end_utf16=_utf16_length(text[:end]),
                page_index=page_index,
                page_input_file_name=page_input_file_name,
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


def _remap_part_syntax_error(
    error: JianpuSyntaxError,
    text: str,
    part_start: int,
) -> JianpuSyntaxError:
    """Re-anchor a part-body syntax error to document coordinates.

    ``_strip_page_marker_lines`` blanks markers in place, so code-point and
    UTF-16 offsets inside the part body align one-to-one with ``text`` from
    ``part_start`` onward.
    """
    token = error.token
    base_utf16 = _utf16_length(text[:part_start])
    return JianpuSyntaxError(
        _Token(
            value=token.value,
            line=text.count("\n", 0, part_start) + token.line,
            column=token.column,
            start_utf16=(
                base_utf16 + token.start_utf16
                if token.start_utf16 is not None
                else None
            ),
            end_utf16=(
                base_utf16 + token.end_utf16 if token.end_utf16 is not None else None
            ),
            measure=token.measure,
        ),
        error.detail,
    )


@dataclass(slots=True)
class _PreviewRecovery:
    """Per-request recovery; strict parsing never creates this state."""

    errors: dict[int, JianpuSyntaxError] = field(default_factory=dict)
    lexical_errors: dict[int, JianpuSyntaxError] = field(default_factory=dict)
    context_warnings: dict[str, SyntaxDiagnostic] = field(default_factory=dict)
    warnings: dict[int, list[SyntaxDiagnostic]] = field(default_factory=dict)
    profiles: dict[int, InstrumentProfile] = field(default_factory=dict)

    def setting_valid(self, name: str) -> None:
        self.context_warnings.pop(name, None)

    def failed(self, index: int, error: JianpuSyntaxError) -> None:
        self.errors.setdefault(index, error)
        raw = error.token.value.strip()
        setting = None
        if raw.startswith("1=") or re.match(r"^1\s*=", raw):
            setting = "调号"
        elif re.fullmatch(r"\d+/\d+", raw):
            setting = "拍号"
        elif raw.startswith("tempo"):
            setting = "速度"
        elif raw.startswith("instrument"):
            setting = "乐器模式"
        if setting:
            diagnostic = error.diagnostic()
            self.context_warnings[setting] = diagnostic.model_copy(
                update={
                    "id": "live-context-" + diagnostic.id,
                    "severity": "warning",
                    "message": f"此前{setting}设置无效，当前预览沿用最近有效设置（未设置时使用默认值）。",
                }
            )


def parse_jianpu_score(
    text: str,
    *,
    title: str | None = None,
    _initial_tempo: int = DEFAULT_TEMPO,
) -> JianpuScore:
    normalized = text.lstrip("\ufeff")
    options, token_lines, lyrics = _read_new_syntax(normalized)
    return _parse_score_tokens(
        options, token_lines, lyrics, title=title, initial_tempo=_initial_tempo
    )


def _parse_score_tokens(
    options: JianpuOptions,
    token_lines: list[_Token],
    lyrics: list[str],
    *,
    title: str | None = None,
    initial_tempo: int = DEFAULT_TEMPO,
    recovery: _PreviewRecovery | None = None,
) -> JianpuScore:
    if title is not None and options.title is None:
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
    repeat_applied_backward = False
    measure_number = 1
    next_repeat_start = False
    current_key = options.key
    current_beats = options.beats
    current_beat_type = options.beat_type
    current_tempo = options.tempo or initial_tempo
    pending_slide_token: _Token | None = None
    skip_empty_bar_after_repeat_end = False
    measure_source_start_utf16: int | None = None
    # 声线（& 分隔）：cursor 始终跟踪当前声线；跨小节的连音线/连线/滑音
    # 状态按声线隔离，避免 lane 1 末尾的 tie 错误地连到 lane 2 开头。
    current_lane = 1
    current_event_lanes: list[int] = []
    events_in_current_lane = 0
    open_slur_by_lane: dict[int, bool] = {}
    open_tie_by_lane: dict[int, bool] = {}
    last_pitched_by_lane: dict[int, Event] = {}
    # 诊断定位：小节首个 token（超拍等小节级错误指向小节开头而非小节线），
    # 以及每条声线的引入 & token（空声线错误的定位点）。
    measure_first_token: _Token | None = None
    lane_separator_tokens: dict[int, _Token] = {}

    discarding = False
    connections_uncertain = False
    slide_undo: list[tuple[Event, bool, SlideDirection | None]] = []

    def flush_measure(
        *,
        preserve_empty: bool = False,
        boundary_token: _Token | None = None,
    ) -> None:
        nonlocal \
            current_events, \
            current_blocks, \
            cursor, \
            measure_number, \
            next_repeat_start, \
            measure_articulations, \
            measure_ornaments, \
            pending_repeat_count, \
            repeat_applied_backward, \
            measure_source_start_utf16, \
            current_lane, \
            current_event_lanes, \
            events_in_current_lane, \
            measure_first_token, \
            lane_separator_tokens

        def reset_lane_state() -> None:
            nonlocal current_lane, current_event_lanes, events_in_current_lane
            nonlocal measure_first_token, lane_separator_tokens
            current_lane = 1
            current_event_lanes = []
            events_in_current_lane = 0
            measure_first_token = None
            lane_separator_tokens = {}

        def lane_error_token(lane: int, fallback: _Token | None) -> _Token | None:
            """小节级声线错误的定位 token：行列指向小节开头，范围覆盖整小节
            （这样 validate 的 mask 重试会遮蔽整个出错小节，不会因只遮蔽
            小节线而把内容并入下一行小节、级联出重复的错位诊断）。
            """
            base = measure_first_token or fallback
            if base is None:
                return None
            end_utf16 = (
                fallback.end_utf16
                if fallback is not None and fallback.end_utf16 is not None
                else base.end_utf16
            )
            return _Token(
                value=base.value,
                line=base.line,
                column=base.column,
                start_utf16=measure_source_start_utf16,
                end_utf16=end_utf16,
                measure=fallback.measure if fallback is not None else base.measure,
            )

        if current_lane > 1 and events_in_current_lane == 0:
            separator = lane_separator_tokens.get(current_lane)
            raise _contextual_syntax_error(
                separator or boundary_token,
                f"声线分隔符 & 之后的第 {current_lane} 声线不能为空",
            )
        if not current_events and not current_blocks:
            reset_lane_state()
            if repeat_applied_backward:
                repeat_applied_backward = False
                measure_articulations = []
                measure_ornaments = []
                measure_source_start_utf16 = None
                return
            if preserve_empty:
                current_events = [
                    Event(
                        kind="rest",
                        duration=Fraction(current_beats * 4, current_beat_type),
                        start=Fraction(0, 1),
                        generated=True,
                        hidden=True,
                        measure_rest=True,
                    )
                ]
                current_event_lanes = [1]
                if measure_source_start_utf16 is None and boundary_token is not None:
                    measure_source_start_utf16 = boundary_token.start_utf16
            else:
                measure_articulations = []
                measure_ornaments = []
                measure_source_start_utf16 = None
                return
        # 多声线小节：为所有事件打上 voice 标签（声线序号），
        # 并严格校验每条声线不超出小节时值（对齐是 & 语法的前提）。
        if current_lane > 1:
            for event, lane in zip(current_events, current_event_lanes, strict=True):
                event.voice = str(lane)
            target = Fraction(current_beats * 4, current_beat_type)
            lane_ends: dict[int, Fraction] = {}
            for event, lane in zip(current_events, current_event_lanes, strict=True):
                end = (event.start or Fraction(0, 1)) + event.duration
                if end > lane_ends.get(lane, Fraction(0, 1)):
                    lane_ends[lane] = end
            for lane, end in sorted(lane_ends.items()):
                if end > target:
                    raise _contextual_syntax_error(
                        lane_error_token(lane, boundary_token),
                        f"第 {lane} 声线超拍：实际 {end}，小节时值 {target}。"
                        "请检查 & 分隔的每条声线时长不超过小节总时值。",
                    )
        source_end_utf16 = (
            boundary_token.end_utf16
            if boundary_token is not None
            else max(
                (
                    event.source_end_utf16
                    for event in current_events
                    if event.source_end_utf16 is not None
                ),
                default=measure_source_start_utf16,
            )
        )
        measure = Measure(
            source_number=str(measure_number),
            duration=Fraction(current_beats * 4, current_beat_type),
            events=current_events,
            text_blocks=current_blocks,
            beats_per_measure=current_beats,
            beat_type=current_beat_type,
            tempo=current_tempo,
            source_key=current_key,
            target_key=current_key,
            repeat_start=next_repeat_start,
            repeat_count=pending_repeat_count,
            source_start_utf16=measure_source_start_utf16,
            source_end_utf16=source_end_utf16,
        )
        _normalize_parsed_measure(measure)
        if recovery is not None:
            recovery.profiles[len(score.measures)] = options.instrument_profile
            recovery.warnings[len(score.measures)] = list(
                recovery.context_warnings.values()
            )
        score.measures.append(measure)
        slide_undo.clear()
        current_events = []
        current_blocks = []
        cursor = Fraction(0, 1)
        measure_number += 1
        next_repeat_start = False
        measure_articulations = []
        measure_ornaments = []
        pending_repeat_count = 1
        measure_source_start_utf16 = None
        reset_lane_state()

    def append_event(event: Event, raw: str, token: _Token | None = None) -> None:
        nonlocal \
            cursor, \
            pending_dynamic, \
            pending_articulations, \
            pending_ornaments, \
            pending_technical, \
            pending_slide, \
            pending_slide_token, \
            repeat_applied_backward, \
            measure_source_start_utf16, \
            events_in_current_lane, \
            measure_first_token
        event.source_token = raw
        if token is not None:
            event.source_start_utf16 = token.start_utf16
            event.source_end_utf16 = token.end_utf16
        event.start = cursor
        if pending_dynamic and event.dynamic is None:
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
            pending_slide_token = None
        if event.slide_stop:
            if event.kind != "note":
                raise _contextual_syntax_error(
                    token, "连线滑音 ^lh 后必须跟随音符，不能跟休止符"
                )
            lane_last_pitched = last_pitched_by_lane.get(current_lane)
            if lane_last_pitched is None:
                raise _contextual_syntax_error(
                    token, "连线滑音 ^lh 前没有可连接的起始音"
                )
            if recovery is not None:
                slide_undo.append(
                    (
                        lane_last_pitched,
                        lane_last_pitched.slide_start,
                        lane_last_pitched.slide_direction,
                    )
                )
            lane_last_pitched.slide_start = True
            _set_slide_direction(
                lane_last_pitched,
                event,
                instrument_profile=options.instrument_profile,
                token=token,
            )
        if connections_uncertain:
            if (
                event.slur_stop
                and not event.slur_start
                and not open_slur_by_lane.get(current_lane)
            ):
                raise _contextual_syntax_error(
                    token, "此前小节有语法错误，连音线的起点不可确定"
                )
            if (
                event.tie_stop
                and not event.tie_start
                and not open_tie_by_lane.get(current_lane)
            ):
                raise _contextual_syntax_error(
                    token, "此前小节有语法错误，延音线的起点不可确定"
                )
        if event.slur_start:
            open_slur_by_lane[current_lane] = True
        if event.slur_stop and open_slur_by_lane.get(current_lane):
            open_slur_by_lane[current_lane] = False
        # Propagate tie across measures: if a previous note had tie_start,
        # the next note automatically receives tie_stop even without explicit ~
        # （按声线隔离：lane 1 末尾的 tie 只连到下一小节的 lane 1）
        if open_tie_by_lane.get(current_lane) and not event.tie_stop:
            event.tie_stop = True
        if event.tie_start:
            open_tie_by_lane[current_lane] = True
        elif event.tie_stop:
            open_tie_by_lane[current_lane] = False
        for pitch in event.pitches:
            if pitch.accidental_text in {"n", "♮"}:
                _step, key_alter, _octave = jianpu_pitch_to_written(
                    pitch.degree,
                    Fraction(0, 1),
                    pitch.octave,
                    current_key,
                )
                pitch.accidental = -key_alter
        normalize_event_marks(event)
        _validate_instrument_mark_target(event, options.instrument_profile, token=token)
        if measure_source_start_utf16 is None and token is not None:
            measure_source_start_utf16 = token.start_utf16
            measure_first_token = token
        repeat_applied_backward = False
        current_events.append(event)
        current_event_lanes.append(current_lane)
        events_in_current_lane += 1
        cursor += event.duration
        if event.kind == "note":
            last_pitched_by_lane[current_lane] = event

    def remember_measure_token(token: _Token) -> None:
        nonlocal measure_source_start_utf16, measure_first_token
        if measure_source_start_utf16 is None:
            measure_source_start_utf16 = token.start_utf16
            measure_first_token = token

    def recover_measure(boundary: _Token | None) -> None:
        nonlocal current_events, current_blocks, current_lane, events_in_current_lane
        nonlocal cursor, pending_dynamic, pending_slide, pending_slide_token, discarding
        nonlocal repeat_applied_backward, connections_uncertain
        connections_uncertain = True
        for event, slide_start, direction in slide_undo:
            event.slide_start = slide_start
            event.slide_direction = direction
        slide_undo.clear()
        current_events = []
        current_blocks = []
        current_lane = 1
        events_in_current_lane = 0
        cursor = Fraction(0)
        pending_dynamic = None
        pending_articulations.clear()
        pending_ornaments.clear()
        pending_technical.clear()
        pending_slide = False
        pending_slide_token = None
        open_slur_by_lane.clear()
        open_tie_by_lane.clear()
        last_pitched_by_lane.clear()
        repeat_applied_backward = False
        flush_measure(preserve_empty=True, boundary_token=boundary)
        discarding = False

    for token in token_lines:
        raw = token.value
        boundary = raw in {"|", "||", "|:", ":|"}
        if discarding:
            if re.fullmatch(r"\*\d+", raw):
                pending_repeat_count = max(1, int(raw[1:]))
            if not boundary:
                continue
            recover_measure(token)
            if raw == "|:":
                next_repeat_start = True
                remember_measure_token(token)
            elif raw == ":|":
                score.measures[-1].repeat_end = True
                skip_empty_bar_after_repeat_end = True
            continue
        try:
            if recovery is not None and token.start_utf16 in recovery.lexical_errors:
                raise recovery.lexical_errors[token.start_utf16]
            if skip_empty_bar_after_repeat_end and raw not in {"|", "||"}:
                skip_empty_bar_after_repeat_end = False
            if recovery is not None and raw.startswith("instrument="):
                options.instrument_profile = normalize_instrument_profile(
                    raw.split("=", 1)[1]
                )
                recovery.setting_valid("乐器模式")
                continue
            key_signature = _key_signature_value(raw)
            if key_signature is not None:
                if current_events:
                    raise _syntax_error(
                        token,
                        f"调号 {raw} 必须写在该小节音符之前，不能写在音符后面。"
                        "请把调号移到小节开头或紧跟在小节线 | 之后。",
                    )
                if score.measures and not token.standalone_line:
                    remember_measure_token(token)
                if recovery is not None:
                    recovery.setting_valid("调号")
                current_key = key_signature
                continue
            if _is_tempo_token(raw):
                if current_events:
                    raise _syntax_error(
                        token,
                        f"速度 {raw} 必须写在该小节音符之前，不能写在音符后面。"
                        "请把速度移到小节开头或紧跟在小节线 | 之后。",
                    )
                if score.measures and not token.standalone_line:
                    remember_measure_token(token)
                current_tempo = _parse_tempo_token(token)
                if recovery is not None:
                    recovery.setting_valid("速度")
                continue
            time_signature = _time_signature_value(raw)
            if time_signature is not None:
                if current_events:
                    raise _syntax_error(
                        token,
                        f"拍号 {raw} 必须写在该小节音符之前，不能写在音符后面。"
                        "请把拍号移到小节开头或紧跟在小节线 | 之后。",
                    )
                if score.measures and not token.standalone_line:
                    remember_measure_token(token)
                if recovery is not None:
                    recovery.setting_valid("拍号")
                current_beats, current_beat_type = time_signature
                continue
            if re.fullmatch(r"\d+/\d+", raw):
                raise _syntax_error(token, f"拍号无效：{raw}，分子分母必须为正整数")
            if raw == "&":
                # 声线分隔：结束当前声线，下一条声线从小节起点重新开始计时。
                if not current_event_lanes:
                    raise _syntax_error(
                        token,
                        "声线分隔符 & 不能出现在小节开头，请先写第 1 声线的内容",
                    )
                if events_in_current_lane == 0:
                    raise _syntax_error(
                        token, "声线分隔符 & 不能连续出现，每条声线至少一个事件"
                    )
                if pending_slide:
                    raise _syntax_error(token, "连线滑音 ^lh 不能跨声线连接")
                current_lane += 1
                lane_separator_tokens[current_lane] = token
                events_in_current_lane = 0
                cursor = Fraction(0, 1)
                continue
            if raw in {"|", "||"}:
                flush_measure(
                    preserve_empty=not skip_empty_bar_after_repeat_end,
                    boundary_token=token,
                )
                skip_empty_bar_after_repeat_end = False
                continue
            if raw == "|:":
                flush_measure(boundary_token=token)
                next_repeat_start = True
                remember_measure_token(token)
                continue
            if raw == ":|":
                flush_measure(boundary_token=token)
                if score.measures:
                    score.measures[-1].repeat_end = True
                skip_empty_bar_after_repeat_end = True
                continue
            if re.fullmatch(r"\*\d+", raw):
                repeat_count = max(1, int(raw[1:]))
                if (
                    not current_events
                    and not current_blocks
                    and score.measures
                    and not next_repeat_start
                ):
                    previous = score.measures[-1]
                    previous.repeat_count = repeat_count
                    if token.end_utf16 is not None and (
                        previous.source_end_utf16 is None
                        or token.end_utf16 > previous.source_end_utf16
                    ):
                        previous.source_end_utf16 = token.end_utf16
                    repeat_applied_backward = True
                else:
                    remember_measure_token(token)
                    pending_repeat_count = repeat_count
                continue

            measure_mark = _measure_level_mark(raw)
            if measure_mark is not None:
                remember_measure_token(token)
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
                remember_measure_token(token)
                dynamic = raw[1:]
                if dynamic not in DYNAMICS:
                    inline_marks, event_part = _consume_tuplet_inline_marks(raw)
                    if not inline_marks or not event_part:
                        raise _syntax_error(
                            token,
                            f"不支持的力度标记：{raw}，请使用 \\p、\\mp、\\f、\\ff 等",
                        )
                    event_offset = raw.find(event_part)
                    event_token = _Token(
                        event_part,
                        token.line,
                        token.column + event_offset,
                        start_utf16=(
                            token.start_utf16 + _utf16_length(raw[:event_offset])
                            if token.start_utf16 is not None
                            else None
                        ),
                        end_utf16=(
                            token.start_utf16
                            + _utf16_length(raw[:event_offset])
                            + _utf16_length(event_part)
                            if token.start_utf16 is not None
                            else None
                        ),
                        measure=token.measure,
                    )
                    event = _parse_event_token(event_token)
                    _apply_inline_marks(event, inline_marks)
                    append_event(event, raw, token)
                    continue
                pending_dynamic = dynamic
                continue
            if raw.startswith("^"):
                remember_measure_token(token)
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
                        start_utf16=(
                            token.start_utf16 + _utf16_length(raw[:event_offset])
                            if token.start_utf16 is not None
                            else None
                        ),
                        end_utf16=(
                            token.start_utf16
                            + _utf16_length(raw[:event_offset])
                            + _utf16_length(event_part)
                            if token.start_utf16 is not None
                            else None
                        ),
                        measure=token.measure,
                    )
                    event = _parse_event_token(event_token)
                    _apply_inline_marks(event, inline_marks)
                    append_event(event, raw, token)
                    continue
                kind, mark = _mark_kind_name(name)
                if kind == "spanner":
                    pending_slide = True
                    pending_slide_token = token
                    continue
                if kind == "ornament":
                    pending_ornaments.append(mark)
                elif kind == "technical":
                    pending_technical.append(mark)
                else:
                    pending_articulations.append(mark)
                continue
            if _is_tuplet_token(raw):
                for event, source_token in _parse_tuplet_token(token):
                    append_event(event, source_token, token)
                continue

            append_event(_parse_event_token(token), raw, token)

        except JianpuSyntaxError as exc:
            if recovery is None:
                raise
            recovery.failed(len(score.measures), exc)
            remember_measure_token(token)
            discarding = True
            if boundary:
                recover_measure(token)
                if raw == "|:":
                    next_repeat_start = True
                    remember_measure_token(token)
                elif raw == ":|":
                    score.measures[-1].repeat_end = True
                    skip_empty_bar_after_repeat_end = True

    if discarding:
        recover_measure(token_lines[-1] if token_lines else None)
    if pending_slide:
        error = _contextual_syntax_error(
            pending_slide_token, "连线滑音 ^lh 后必须跟随目标音符"
        )
        if recovery is None:
            raise error
        index = len(score.measures)
        if not current_events and score.measures:
            index -= 1
        recovery.failed(index, error)
    if current_events or current_blocks or not score.measures:
        try:
            flush_measure()
        except JianpuSyntaxError as exc:
            if recovery is None:
                raise
            recovery.failed(len(score.measures), exc)
            recover_measure(token_lines[-1] if token_lines else None)

    if recovery is not None and recovery.errors and lyrics:
        first_error = min(recovery.errors)
        _apply_lyrics(JianpuScore(measures=score.measures[:first_error]), lyrics)
        diagnostic = recovery.errors[first_error].diagnostic()
        warning = diagnostic.model_copy(
            update={
                "id": "live-lyrics-" + diagnostic.id,
                "severity": "warning",
                "message": "此前小节有语法错误，歌词对齐无法确定，当前预览暂不显示歌词。",
            }
        )
        for index in range(first_error + 1, len(score.measures)):
            recovery.warnings.setdefault(index, []).append(warning)
    else:
        _apply_lyrics(score, lyrics)
    current_number = 1
    for measure in score.measures:
        measure.display_number = current_number
        current_number += measure.repeat_count
    return score


def _read_new_syntax(
    text: str, *, recovery: _PreviewRecovery | None = None
) -> tuple[JianpuOptions, list[_Token], list[str]]:
    """读取新语法，产出 token 流。

    注意：token 的 `measure` 是**整篇文档的累计小节线计数**。按页连续的显示号
    由 `_relabel_measure_numbers` 事后重打，因为准确的分段需要 `parse_jianpu_parts`
    的结果，而解析会失败（文档本身有语法错误时正是最需要正确号号的场景）。
    """
    options = JianpuOptions()
    tokens: list[_Token] = []
    lyrics: list[str] = []
    saw_key = False
    saw_score_tokens = False
    current_measure = 1
    pending_repeat = 1
    saw_token_since_bar = False
    # T8：以下四个状态让 current_measure 的推进对齐 flush_measure 的语义
    # （|:/:| 不产生空小节、:| 之后的空小节吞掉、backward *N 之后的空小节吞掉）。
    skip_empty = False
    repeat_applied_backward = False
    after_repeat_start = False
    has_measures = False
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
        try:
            if "=" in stripped and not stripped.startswith(
                ("|", ":", "[", "\\", "^", "$")
            ):
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
                                measure=str(current_measure),
                                standalone_line=True,
                            )
                        )
                        saw_token_since_bar = True
                    else:
                        options.key = value
                        saw_key = True
                    continue
                if key == "title":
                    options.title = value or options.title
                    continue
                if key == "tempo" and re.fullmatch(r"[^\s|]+", value):
                    tempo_token = _token_with_offsets(
                        stripped,
                        line_no,
                        raw_line.find(stripped),
                        line_utf16_starts[line_no - 1],
                        original_line,
                        measure=str(current_measure),
                        standalone_line=saw_score_tokens,
                    )
                    tempo = _parse_tempo_token(tempo_token)
                    if saw_score_tokens:
                        tokens.append(tempo_token)
                        saw_token_since_bar = True
                    else:
                        options.tempo = tempo
                    continue
                if key == "instrument":
                    if value not in ACCEPTED_INSTRUMENT_PROFILES:
                        raise JianpuSyntaxError(
                            _token_with_offsets(
                                stripped,
                                line_no,
                                raw_line.find(stripped),
                                line_utf16_starts[line_no - 1],
                                original_line,
                            ),
                            f"不支持的乐器模式 {value}，"
                            "请使用 " + "、".join(SUPPORTED_INSTRUMENT_PROFILES),
                        )
                    if recovery is not None and saw_score_tokens:
                        tokens.append(
                            _token_with_offsets(
                                "instrument=" + value,
                                line_no,
                                raw_line.find(stripped),
                                line_utf16_starts[line_no - 1],
                                original_line,
                                measure=str(current_measure),
                                standalone_line=True,
                            )
                        )
                    else:
                        options.instrument_profile = normalize_instrument_profile(value)
                    continue
            if re.fullmatch(r"\d+/\d+", stripped):
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
                            measure=str(current_measure),
                            standalone_line=True,
                        )
                    )
                    saw_token_since_bar = True
                else:
                    if int(beats) <= 0 or int(beat_type) <= 0:
                        raise JianpuSyntaxError(
                            _token_with_offsets(
                                stripped,
                                line_no,
                                raw_line.find(stripped),
                                line_utf16_starts[line_no - 1],
                                original_line,
                            ),
                            f"拍号无效：{stripped}，分子分母必须为正整数",
                        )
                    options.beats = int(beats)
                    options.beat_type = int(beat_type)
                continue
        except JianpuSyntaxError as exc:
            if recovery is None:
                raise
            recovery.lexical_errors[exc.token.start_utf16 or 0] = exc
            tokens.append(exc.token)
            saw_token_since_bar = True
            saw_score_tokens = True
            continue
        for match in re.finditer(
            (
                r"\(?\$[^$|]+\$\)?|\|\||\|:|:\||\||&|[^\s|&]+"
                if recovery is not None
                else r"\(?\$[^$]+\$\)?|\|\||\|:|:\||\||&|[^\s|&]+"
            ),
            raw_line,
        ):
            raw_token = match.group(0)
            if _is_measure_label_token(raw_token):
                continue
            original_column = original_line.find(raw_line)
            original_column = max(original_column, 0)
            token = _token_with_offsets(
                raw_token,
                line_no,
                original_column + match.start(),
                line_utf16_starts[line_no - 1],
                original_line,
                measure=str(current_measure),
            )
            tokens.append(token)
            if not _is_key_or_time_token(raw_token):
                saw_score_tokens = True
            if raw_token in {"|", "||", "|:", ":|"}:
                # 对齐 flush_measure：有内容才推进 pending_repeat 个号；空小节按规则吞并。
                if saw_token_since_bar:
                    current_measure += pending_repeat
                    has_measures = True
                    after_repeat_start = False
                elif repeat_applied_backward:
                    # backward *N 之后的空小节被吞掉，不再推进。
                    repeat_applied_backward = False
                elif raw_token in {"|", "||"} and not skip_empty:
                    # 非 :| 之后的空小节保留为整小节休止，占 1 个号。
                    current_measure += 1
                    has_measures = True
                # |: / :| 自身的空 flush 不产生小节。
                pending_repeat = 1
                saw_token_since_bar = False
                if raw_token == "|:":
                    after_repeat_start = True
                elif raw_token == ":|":
                    skip_empty = True
                else:
                    skip_empty = False
            elif re.fullmatch(r"\*\d+", raw_token):
                repeat_n = max(1, int(raw_token[1:]))
                if not saw_token_since_bar and has_measures and not after_repeat_start:
                    # backward：覆盖上一小节的反复次数（扩展占号，不新增小节）。
                    current_measure += repeat_n - 1
                    repeat_applied_backward = True
                else:
                    pending_repeat = repeat_n
            else:
                saw_token_since_bar = True
    return options, tokens, lyrics


def _token_with_offsets(
    value: str,
    line: int,
    column: int,
    line_start_utf16: int,
    original_line: str,
    *,
    measure: str | None = None,
    standalone_line: bool = False,
) -> _Token:
    return _Token(
        value=value,
        line=line,
        column=max(0, column) + 1,
        start_utf16=_utf16_length(original_line[: max(0, column)]) + line_start_utf16,
        end_utf16=_utf16_length(original_line[: max(0, column) + len(value)])
        + line_start_utf16,
        measure=measure,
        standalone_line=standalone_line,
    )


def _is_key_or_time_token(token: str) -> bool:
    return (
        _key_signature_value(token) is not None
        or _time_signature_value(token.strip()) is not None
    )


def _is_tempo_token(token: str) -> bool:
    return bool(re.match(r"^tempo\s*=", token.strip()))


def _parse_tempo_token(token: _Token) -> int:
    match = re.fullmatch(r"tempo\s*=\s*([^\s|]+)", token.value.strip())
    value = match.group(1) if match else ""
    try:
        tempo = int(value)
    except ValueError:
        tempo = 0
    if not MIN_TEMPO <= tempo <= MAX_TEMPO or str(tempo) != value:
        raise JianpuSyntaxError(
            token,
            f"tempo 必须是 {MIN_TEMPO} 到 {MAX_TEMPO} 之间的整数：{value}",
        )
    return tempo


def _strip_inline_comment(line: str) -> str:
    comment_start = line.find("//")
    if comment_start < 0:
        return line
    return line[:comment_start]


def _strip_leading_measure_label(line: str) -> str:
    match = re.match(r"^\s*(\d+)([.:：])(?P<gap>\s+|$)", line)
    if match is None:
        return line
    number = int(match.group(1))
    separator = match.group(2)
    # 与 _is_measure_label_token 规则对齐：
    # 冒号分隔（AI 小节编号，如 "272:"）或点号分隔且数字 >7（如 "10."）才按标签剥离；
    # 点号分隔且 0<=N<=7（如 "1."、"0."）按附点音符处理，不剥离（否则吞掉合法音符）。
    if separator in {":", "："}:
        return line[match.end() :]
    if number > 7:
        return line[match.end() :]
    return line


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


def _is_tuplet_token(value: str) -> bool:
    return bool(re.fullmatch(r"\(?\$[^$]+\$\)?", value.strip()))


def _parse_tuplet_token(token: _Token) -> list[tuple[Event, str]]:
    raw_value = token.value
    stripped_value = raw_value.strip()
    outer_slur_start = stripped_value.startswith("($")
    outer_slur_stop = stripped_value.endswith("$)")
    if outer_slur_start:
        stripped_value = stripped_value[1:]
    if outer_slur_stop:
        stripped_value = stripped_value[:-1]
    inner = stripped_value[1:-1]
    # Code-point offset of the tuplet body inside ``raw_value`` so inner tokens
    # can be re-anchored to the outer token's UTF-16 offsets.
    body_offset = (
        (len(raw_value) - len(raw_value.lstrip()))
        + int(outer_slur_start)
        + 1
        + (len(inner) - len(inner.lstrip()))
    )
    body = inner.strip()
    if "&" in body:
        raise _syntax_error(
            token, "连音组内不允许声线分隔符 &，声线切换只能在小节顶层进行"
        )
    explicit_ratio, body, ratio_offset = _consume_tuplet_ratio(body, token)
    body_offset += ratio_offset
    parts = _split_tuplet_body(body)
    pending_dynamic: str | None = None
    pending_articulations: list[str] = []
    pending_ornaments: list[str] = []
    pending_technical: list[str] = []
    parsed: list[tuple[Event, str]] = []
    search_from = 0
    for part in parts:
        part_offset = body.find(part, search_from)
        if part_offset < 0:
            part_offset = search_from
        search_from = part_offset + len(part)
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
        event_offset_in_part = (len(part) - len(part.lstrip())) + (
            len(part.strip()) - len(event_part)
        )
        event_offset_in_value = body_offset + part_offset + event_offset_in_part
        part_token = _Token(
            event_part,
            token.line,
            token.column + event_offset_in_value,
            start_utf16=(
                token.start_utf16 + _utf16_length(raw_value[:event_offset_in_value])
                if token.start_utf16 is not None
                else None
            ),
            end_utf16=(
                token.start_utf16
                + _utf16_length(raw_value[:event_offset_in_value])
                + _utf16_length(event_part)
                if token.start_utf16 is not None
                else None
            ),
            measure=token.measure,
        )
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
    if has_explicit_duration:
        raise _syntax_error(
            token,
            "连音组内不允许时值前缀，请用 $实际数:常规数;$ 比例或默认 $...$",
        )
    if explicit_ratio is not None:
        actual_count, normal_count = explicit_ratio
    else:
        actual_count = len(parsed)
        normal_count = tuplet_normal_notes(actual_count)
    group_id = f"{token.line}:{token.column}"
    events: list[tuple[Event, str]] = []
    for index, (event, source_token) in enumerate(parsed):
        if explicit_ratio is not None:
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
    if outer_slur_start:
        events[0][0].slur_start = True
    if outer_slur_stop:
        events[-1][0].slur_stop = True
    return events


def _consume_tuplet_ratio(
    body: str,
    token: _Token,
) -> tuple[tuple[int, int] | None, str, int]:
    match = re.match(r"^(\d+)\s*:\s*(\d+)\s*;", body)
    if match is None:
        return None, body, 0
    actual_count = int(match.group(1))
    normal_count = int(match.group(2))
    if actual_count <= 0 or normal_count <= 0:
        raise _syntax_error(token, "连音组比例必须是正整数，例如 $3:2;q1 q2$")
    remainder = body[match.end() :]
    offset = match.end() + (len(remainder) - len(remainder.lstrip()))
    return (actual_count, normal_count), remainder.strip(), offset


def _has_tuplet_duration_prefix(source_token: str) -> bool:
    work = source_token.strip().lstrip("(~")
    return bool(duration_prefix(work))


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
    inline_marks, work = _consume_tuplet_inline_marks(work)
    has_duration_prefix = bool(duration_prefix(work))
    duration, work = consume_duration_prefix(work)
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
    if inline_marks:
        _apply_inline_marks(event, inline_marks)
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
        accidental_text = "n"
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
            # 多声线小节（& 语法）的歌词只归属第 1 声线
            if event.voice not in (None, "1"):
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
    token: _Token | None = None,
) -> None:
    if len(start.pitches) != 1 or len(stop.pitches) != 1:
        if instrument_profile == "guzheng":
            raise _contextual_syntax_error(
                token, "古筝有时值滑音 ^lh 只能连接两个单音，不能连接和弦"
            )
        return
    start_rank = start.pitches[0].rank
    stop_rank = stop.pitches[0].rank
    if start_rank == stop_rank:
        if instrument_profile == "guzheng":
            raise _contextual_syntax_error(
                token, "古筝有时值滑音 ^lh 的起止音高不能相同"
            )
        return
    direction = "up" if stop_rank > start_rank else "down"
    start.slide_direction = direction
    stop.slide_direction = direction


def _validate_instrument_mark_target(
    event: Event,
    instrument_profile: InstrumentProfile,
    *,
    token: _Token | None = None,
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
            raise _contextual_syntax_error(
                token, f"{label}演奏标记 ^{mark.token} 后必须跟随音符"
            )
        if mark.target == "chord" and not event.is_chord:
            raise _contextual_syntax_error(
                token, f"演奏标记 ^{mark.token}（{label}）后必须跟随和弦，例如 [3+5]"
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
    return JianpuSyntaxError(token, message)


def _contextual_syntax_error(token: _Token | None, message: str) -> ValueError:
    if token is None:
        return JianpuSyntaxError(
            _Token(value="", line=1, column=1, start_utf16=0, end_utf16=0),
            message,
        )
    return JianpuSyntaxError(token, message)
