"""Source-preserving, measure-local parsing for the editor preview only."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from ...models.render.live import LiveMeasureSelection
from ..endings import MAX_NOTATION_ENDING_MEASURES, ending_spans
from ...models.score import JianpuScore, Measure
from ...models.syntax.schemas import SyntaxDiagnostic
from .jianpu_text import (
    JianpuSyntaxError,
    ParsedJianpuPart,
    _LYRIC_BLOCK_END,
    _LYRIC_BLOCK_START,
    _PAGE_MARKER_RE,
    _PAGE_MARKER_START_RE,
    _PART_MARKER_RE,
    _PART_MARKER_START_RE,
    _PreviewRecovery,
    _assign_measure_number_bases,
    _line_column_from_utf16_offset,
    _marker_token,
    _parse_score_tokens,
    _read_new_syntax,
    _remap_part_syntax_error,
    _strip_page_marker_lines,
    _utf16_length,
    _utf16_offset_to_codepoint_index,
)


@dataclass(slots=True)
class _Segment:
    start: int
    end: int
    page_index: int = 0
    name: str = ""
    error: JianpuSyntaxError | None = None


def _segments(text: str) -> list[_Segment]:
    parts = list(_PART_MARKER_START_RE.finditer(text))
    pages = list(_PAGE_MARKER_START_RE.finditer(text))
    if not parts:
        # Preserve the existing single-score semantics for documents without @part.
        return [_Segment(0, len(text))]
    result: list[_Segment] = []
    page_cursor = -1
    previous_page = -1
    for index, marker in enumerate(parts):
        while (
            page_cursor + 1 < len(pages)
            and pages[page_cursor + 1].start() < marker.start()
        ):
            page_cursor += 1
        start = marker.end()
        end = parts[index + 1].start() if index + 1 < len(parts) else len(text)
        if page_cursor + 1 < len(pages):
            end = min(end, pages[page_cursor + 1].start())
        # Later-page headers belong to that page's first part, as in strict parsing.
        if result and page_cursor != previous_page:
            start = pages[page_cursor].end()
        previous_page = page_cursor
        valid = _PART_MARKER_RE.fullmatch(marker.group())
        error = None
        name = ""
        if valid:
            try:
                name = json.loads(valid.group("name"))
            except json.JSONDecodeError:
                valid = None
        if not valid:
            error = JianpuSyntaxError(
                _marker_token(text, marker.start(), marker.end()),
                "分谱标记格式无效，无法确定当前预览的声部。",
            )
        if page_cursor >= 0 and not _PAGE_MARKER_RE.fullmatch(
            pages[page_cursor].group()
        ):
            page = pages[page_cursor]
            error = JianpuSyntaxError(
                _marker_token(text, page.start(), page.end()),
                "分页标记格式无效，无法确定当前预览的页面。",
            )
        result.append(_Segment(start, end, max(0, page_cursor), name, error))
    for index, page in enumerate(pages):
        end = pages[index + 1].start() if index + 1 < len(pages) else len(text)
        if not any(page.end() <= part.start() < end for part in parts):
            result.append(
                _Segment(
                    page.end(),
                    end,
                    index,
                    error=JianpuSyntaxError(
                        _marker_token(text, page.start(), page.end()),
                        "当前页面缺少分谱标记，无法确定当前预览的声部。",
                    ),
                )
            )
    return sorted(result, key=lambda segment: segment.start)


def _remap_warning(warning: SyntaxDiagnostic, text: str, base: int) -> SyntaxDiagnostic:
    start = base + warning.start
    end = base + warning.end
    line, column = _line_column_from_utf16_offset(text, start)
    return warning.model_copy(
        update={
            "start": start,
            "end": end,
            "line": line,
            "column": column,
            "id": f"{warning.id}-{base}",
        }
    )


def _parse_live_segment(
    stripped_body: str, block_rel_cp: int | None
) -> tuple[JianpuScore, _PreviewRecovery]:
    """解析一个 segment；歌词块错误时容错降级，保证编辑歌词时预览不中断。

    两级降级：块未闭合先虚拟补结束符（正在输入的歌词仍可附着到音符）；
    其余歌词错误（内容/`&` 流/溢出谱面等，token 偏移落在块内）则把块起到
    段尾掩码为空格（保留换行），无歌词重解析。歌词块之外的错误照常上抛。
    """

    def _parse(candidate: str) -> tuple[JianpuScore, _PreviewRecovery]:
        recovery = _PreviewRecovery()
        options, tokens, lyrics = _read_new_syntax(candidate, recovery=recovery)
        score = _parse_score_tokens(
            options, tokens, lyrics, title="", recovery=recovery
        )
        return score, recovery

    if block_rel_cp is None:
        return _parse(stripped_body)
    block_rel_utf16 = _utf16_length(stripped_body[:block_rel_cp])
    candidates = [stripped_body]
    if _LYRIC_BLOCK_END.search(stripped_body, block_rel_cp + 3) is None:
        candidates.insert(0, stripped_body + " /")
    for candidate in candidates:
        try:
            return _parse(candidate)
        except JianpuSyntaxError as exc:
            start = exc.token.start_utf16
            if start is None or start < block_rel_utf16:
                raise
    masked = "".join(
        char if char in "\r\n" or index < block_rel_cp else " "
        for index, char in enumerate(stripped_body)
    )
    return _parse(masked)


def _project_ending_to_live_measure(
    measures: list[Measure], measure_index: int
) -> Measure:
    """Clip the full-score ending context onto the one-measure live preview."""
    measure = measures[measure_index]
    span = next(
        (
            item
            for item in ending_spans(
                measures, max_measures=MAX_NOTATION_ENDING_MEASURES
            )
            if item.start <= measure_index <= item.stop
        ),
        None,
    )
    projected = replace(
        measure,
        ending_start=None,
        ending_resume=None,
        ending_stop=None,
        ending_discontinue=None,
    )
    if span is None:
        return projected
    if measure_index == span.start:
        projected.ending_start = span.number
    else:
        projected.ending_resume = span.number
    if measure_index == span.stop and not span.discontinue:
        projected.ending_stop = span.number
    else:
        # A clipped segment never gains a right hook merely because the live
        # preview contains only one measure. Actual discontinue has the same ink.
        projected.ending_discontinue = span.number
    return projected


def select_live_measure(
    text: str, cursor_offset: int, *, initial_measure_number: int = 1
) -> LiveMeasureSelection:
    # Mask BOM, rather than removing it, so every offset remains in editor coordinates.
    source = (" " + text[1:]) if text.startswith("\ufeff") else text
    cursor = max(0, min(cursor_offset, _utf16_length(source)))
    cursor_cp = _utf16_offset_to_codepoint_index(source, cursor)
    page_before_cursor = None
    for marker in _PAGE_MARKER_START_RE.finditer(source):
        if marker.start() > cursor_cp:
            break
        page_before_cursor = marker
    if page_before_cursor is not None and not _PAGE_MARKER_RE.fullmatch(
        page_before_cursor.group()
    ):
        raise JianpuSyntaxError(
            _marker_token(source, page_before_cursor.start(), page_before_cursor.end()),
            "分页标记格式无效，无法确定当前预览的页面。",
        )
    # 歌词块定位（全文唯一；多个 /L: 属非法，取第一个做容错）。光标进入块内时
    # 改用「歌词小节 -> 物理小节」的线性映射选中小节，不再依赖 source offset。
    lyric_start = _LYRIC_BLOCK_START.search(source)
    lyric_block_start_cp = lyric_start.start() if lyric_start else None
    cursor_in_lyrics = (
        lyric_block_start_cp is not None and cursor_cp >= lyric_block_start_cp
    )
    lyric_measure_index = (
        source[lyric_start.end() : cursor_cp].count("|") if cursor_in_lyrics else 0
    )
    segments = _segments(source)
    parts: list[ParsedJianpuPart] = []
    recoveries: list[_PreviewRecovery] = []
    selected = 0
    previous_start = 0
    base = 0
    for index, segment in enumerate(segments):
        body = source[segment.start : segment.end]
        block_rel_cp = (
            lyric_block_start_cp - segment.start
            if lyric_block_start_cp is not None
            and segment.start <= lyric_block_start_cp < segment.end
            else None
        )
        score, recovery = _parse_live_segment(
            _strip_page_marker_lines(body), block_rel_cp
        )
        base += _utf16_length(source[previous_start : segment.start])
        previous_start = segment.start
        if base <= cursor:
            selected = index
        for measure in score.measures:
            if measure.source_start_utf16 is not None:
                measure.source_start_utf16 += base
            if measure.source_end_utf16 is not None:
                measure.source_end_utf16 += base
            for event in measure.events:
                if event.source_start_utf16 is not None:
                    event.source_start_utf16 += base
                if event.source_end_utf16 is not None:
                    event.source_end_utf16 += base
        score.part_name = segment.name
        score.part_index = index
        score.page_index = segment.page_index
        parts.append(
            ParsedJianpuPart(
                score=score,
                part_index=index,
                part_name=segment.name,
                body_start_utf16=base,
                body_end_utf16=base + _utf16_length(body),
                page_index=segment.page_index,
            )
        )
        recoveries.append(recovery)
    part = parts[selected]
    segment = segments[selected]
    recovery = recoveries[selected]
    if segment.error:
        raise segment.error
    _assign_measure_number_bases(parts, initial_measure_number=initial_measure_number)
    if not part.score.measures:
        return LiveMeasureSelection(
            score=part.score, initial_measure_number=part.measure_number_base
        )
    block_in_selected = (
        lyric_block_start_cp is not None
        and segment.start <= lyric_block_start_cp < segment.end
    )
    if cursor_in_lyrics and block_in_selected:
        # 光标在歌词区：歌词第 k 个小节线性映射到该声部第 k 个物理小节。
        measure_index = min(lyric_measure_index, len(part.score.measures) - 1)
    else:
        measure_index = 0
        for index, measure in enumerate(part.score.measures):
            if (
                measure.source_end_utf16 is not None
                and measure.source_end_utf16 <= cursor
            ):
                measure_index = index + 1
            elif (
                measure.source_start_utf16 is not None
                and measure.source_start_utf16 <= cursor
            ):
                measure_index = index
        measure_index = min(measure_index, len(part.score.measures) - 1)
    if measure_index in recovery.errors:
        raise _remap_part_syntax_error(
            recovery.errors[measure_index], source, segment.start
        )
    number = part.measure_number_base + sum(
        m.repeat_count for m in part.score.measures[:measure_index]
    )
    measure = _project_ending_to_live_measure(part.score.measures, measure_index)
    return LiveMeasureSelection(
        score=replace(
            part.score,
            title="",
            measures=[measure],
            instrument_profile=recovery.profiles.get(
                measure_index, part.score.instrument_profile
            ),
        ),
        initial_measure_number=number,
        warnings=[
            _remap_warning(w, source, part.body_start_utf16)
            for w in recovery.warnings.get(measure_index, [])
        ],
    )
