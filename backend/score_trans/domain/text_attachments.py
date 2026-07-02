from __future__ import annotations

import re

from ..models.provenance.schemas import (
    BoundingBox,
    SourceElement,
    SourceMap,
    SourceTextAttachment,
    TextPlacementAnchor,
)
from ..models.score import JianpuScore, TextBlock

_NORMALIZE_TEXT = re.compile(r"[\s，。、“”‘’：:；;,.!?！？（）()【】\[\]]+")


def build_source_text_attachments(
    blocks: list[TextBlock],
    score: JianpuScore,
    source_map: SourceMap | None,
    *,
    image_size: tuple[int, int] | None = None,
) -> list[SourceTextAttachment]:
    """Convert OCR output into stable source-space text attachments."""
    sheet = source_map.sheets[0] if source_map and source_map.sheets else None
    width, height = image_size or (
        (sheet.width, sheet.height) if sheet is not None else (0, 0)
    )
    source_ids = _score_source_ids(score)
    candidates = (
        [
            element
            for element in sheet.elements
            if element.source_id in source_ids
            or element.musicxml_locator.contains.startswith("n-")
        ]
        if sheet is not None
        else []
    )
    semantic = _semantic_texts(score)
    attachments: list[SourceTextAttachment] = []
    for index, block in enumerate(blocks):
        text = block.text.strip()
        if (
            not text
            or block.role == "measure_number"
            or _duplicates_semantic_text(block, semantic)
        ):
            continue
        bbox = _source_bbox(block.bbox)
        relative_y = _relative_y(bbox, height)
        anchor = _anchor_for_block(block, bbox, relative_y, candidates, width, height)
        attachments.append(
            SourceTextAttachment(
                id=f"ocr-{index}",
                text=text,
                role=block.role,
                source_bbox=bbox,
                font_size=block.font_size,
                ocr_confidence=block.confidence,
                anchor=anchor,
            )
        )
    return attachments


def _anchor_for_block(
    block: TextBlock,
    bbox: BoundingBox | None,
    relative_y: float | None,
    candidates: list[SourceElement],
    width: int,
    height: int,
) -> TextPlacementAnchor:
    if block.role in {"title", "instrument"}:
        return TextPlacementAnchor(kind="score_start", relative_y=relative_y)
    if block.role == "footer":
        return TextPlacementAnchor(kind="score_end", relative_y=relative_y)
    if bbox is None or not candidates or width <= 0 or height <= 0:
        return TextPlacementAnchor(
            kind="source_relative",
            relative_y=relative_y if relative_y is not None else 0.5,
        )

    candidate, distance = min(
        (
            (
                element,
                _element_distance(block.role, bbox, element, width, height),
            )
            for element in candidates
        ),
        key=lambda item: item[1],
    )
    return TextPlacementAnchor(
        kind="source_element",
        source_id=candidate.source_id,
        relative_y=relative_y,
        mapping_confidence=max(0.0, min(1.0, 1.0 - distance / 3.0)),
    )


def _element_distance(
    role: str,
    block: BoundingBox,
    element: SourceElement,
    width: int,
    height: int,
) -> float:
    block_cx = block.x + block.width / 2
    block_cy = block.y + block.height / 2
    bounds = element.bounds
    element_cx = bounds.x + bounds.width / 2
    element_cy = bounds.y + bounds.height / 2
    horizontal_gap = max(0.0, abs(element_cx - block_cx) - block.width / 2) / width
    vertical_gap = abs(element_cy - block_cy) / height
    direction_penalty = 0.0
    if role == "lyric" and element_cy > block_cy:
        direction_penalty = 1.0
    elif role == "expression" and element_cy < block_cy:
        direction_penalty = 0.5
    return horizontal_gap + vertical_gap * 3.0 + direction_penalty


def _score_source_ids(score: JianpuScore) -> set[str]:
    return {
        source_id
        for measure in score.measures
        for event in measure.events
        for source_id in [
            *event.source_ids,
            *(pitch.source_id for pitch in event.pitches),
        ]
        if source_id
    }


def _semantic_texts(score: JianpuScore) -> dict[str, object]:
    lyrics = [
        normalized
        for measure in score.measures
        for event in measure.events
        if event.lyric and (normalized := _normalize(event.lyric))
    ]
    expressions = {
        normalized
        for measure in score.measures
        for event in measure.events
        if event.dynamic and (normalized := _normalize(event.dynamic))
    }
    for block in [
        *score.text_blocks,
        *(block for measure in score.measures for block in measure.text_blocks),
    ]:
        if block.bbox is not None or not block.text:
            continue
        normalized = _normalize(block.text)
        if block.role == "lyric":
            lyrics.append(normalized)
        elif block.role == "expression":
            expressions.add(normalized)
    return {
        "title": _normalize(score.title),
        "lyrics": set(lyrics),
        "lyric_stream": "".join(lyrics),
        "expressions": expressions,
    }


def _duplicates_semantic_text(block: TextBlock, semantic: dict[str, object]) -> bool:
    text = _normalize(block.text)
    if not text:
        return True
    if block.role == "title":
        return text == semantic["title"]
    if block.role == "lyric":
        lyrics = semantic["lyrics"]
        stream = semantic["lyric_stream"]
        return text in lyrics or text in stream
    if block.role == "expression":
        return text in semantic["expressions"]
    return False


def _normalize(text: str) -> str:
    return _NORMALIZE_TEXT.sub("", text).casefold()


def _source_bbox(
    bbox: tuple[float, float, float, float] | None,
) -> BoundingBox | None:
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return None
    return BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


def _relative_y(bbox: BoundingBox | None, height: int) -> float | None:
    if bbox is None or height <= 0:
        return None
    center = (bbox.y + bbox.height / 2) / height
    return max(0.0, min(1.0, center))
