"""Source-preserving, measure-local parsing for the editor preview only."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from ...models.render.live import LiveMeasureSelection
from ...models.syntax.schemas import SyntaxDiagnostic
from .jianpu_text import (
    JianpuSyntaxError,
    ParsedJianpuPart,
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
    segments = _segments(source)
    parts: list[ParsedJianpuPart] = []
    recoveries: list[_PreviewRecovery] = []
    selected = 0
    previous_start = 0
    base = 0
    for index, segment in enumerate(segments):
        body = source[segment.start : segment.end]
        recovery = _PreviewRecovery()
        options, tokens, lyrics = _read_new_syntax(
            _strip_page_marker_lines(body), recovery=recovery
        )
        score = _parse_score_tokens(
            options, tokens, lyrics, title="", recovery=recovery
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
    measure_index = 0
    for index, measure in enumerate(part.score.measures):
        if measure.source_end_utf16 is not None and measure.source_end_utf16 <= cursor:
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
    measure = part.score.measures[measure_index]
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
