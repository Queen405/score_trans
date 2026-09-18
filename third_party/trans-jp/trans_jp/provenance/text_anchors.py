from __future__ import annotations

from ..models.contracts import RowResult, make_source_id
from .utf16 import utf16_length


def merge_rows(row_results: list[RowResult]) -> tuple[str, list[dict]]:
    merged_text = ""
    anchors: list[dict] = []

    for row_result in row_results:
        if not row_result.jianpu_text:
            continue

        if merged_text and not merged_text.endswith("\n"):
            merged_text += "\n"

        row_start = len(merged_text)
        merged_text += row_result.jianpu_text
        row_text = row_result.jianpu_text

        search_pos = 0
        for token in row_result.tokens:
            source_id = make_source_id(row_result.row.index, token.index)
            found = _find_token_in_text(token.text, row_text, search_pos)
            if found is not None:
                start_cp, end_cp = found
                anchors.append(
                    {
                        "source_id": source_id,
                        "start_utf16": utf16_length(
                            merged_text[: row_start + start_cp]
                        ),
                        "end_utf16": utf16_length(merged_text[: row_start + end_cp]),
                        "role": token.role,
                        "valid": True,
                    }
                )
                search_pos = end_cp
            else:
                anchors.append(
                    {
                        "source_id": source_id,
                        "start_utf16": utf16_length(
                            merged_text[: row_start + search_pos]
                        ),
                        "end_utf16": utf16_length(
                            merged_text[: row_start + search_pos]
                        ),
                        "role": token.role,
                        "valid": False,
                    }
                )

    return merged_text, anchors


def _find_token_in_text(
    token_text: str, row_text: str, start: int
) -> tuple[int, int] | None:
    pos = row_text.find(token_text, start)
    if pos >= 0:
        return pos, pos + len(token_text)
    return None
