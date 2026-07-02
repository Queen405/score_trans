from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import xml.etree.ElementTree as ET

from ..models.provenance.schemas import (
    BoundingBox,
    RenderedTextBlock,
    SourceTextAttachment,
)
from ..models.render.schemas import RenderPageMeasureRange
from ..models.score import TextBlock

_A4_WIDTH = 1240.0
_A4_HEIGHT = 1754.0
_SAFE_X = 84.0
_SAFE_TOP = 120.0
_SAFE_BOTTOM = 84.0


@dataclass(slots=True)
class TextPlacementResult:
    text_blocks_by_page: dict[int, list[TextBlock]]
    rendered_blocks_by_page: dict[int, list[RenderedTextBlock]]


def place_source_text_attachments(
    attachments_by_source_page: list[list[SourceTextAttachment]],
    layout_svgs: list[str],
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
) -> TextPlacementResult:
    anchor_lookup = _render_anchor_lookup(layout_svgs)
    text_blocks: dict[int, list[TextBlock]] = defaultdict(list)
    rendered: dict[int, list[RenderedTextBlock]] = defaultdict(list)
    lanes: dict[tuple[int, int, str], int] = defaultdict(int)
    header_lane = 0
    footer_lane = 0

    for source_page_index, attachments in enumerate(attachments_by_source_page):
        for attachment in attachments:
            anchor = attachment.anchor
            if anchor.kind == "score_start":
                page_index = 0
                anchor_box = BoundingBox(
                    x=_SAFE_X,
                    y=_SAFE_TOP + header_lane * 30.0,
                    width=1,
                    height=1,
                )
                header_lane += 1
            elif anchor.kind == "score_end":
                page_index = max(0, len(layout_svgs) - 1)
                anchor_box = BoundingBox(
                    x=_SAFE_X,
                    y=_A4_HEIGHT - _SAFE_BOTTOM - 28.0 - footer_lane * 30.0,
                    width=1,
                    height=1,
                )
                footer_lane += 1
            else:
                page_index, anchor_box = _source_anchor_target(
                    source_page_index,
                    attachment,
                    anchor_lookup,
                    measure_ranges_by_page,
                )

            font_size = _font_size(attachment.font_size)
            width = _text_width(attachment, font_size)
            placement = _placement(attachment.role)
            lane_key = (
                page_index,
                round((anchor_box.x + anchor_box.width / 2) / 160),
                placement,
            )
            lane = lanes[lane_key]
            lanes[lane_key] += 1
            bbox = _render_bbox(
                attachment,
                anchor_box,
                width,
                font_size,
                placement,
                lane,
            )
            block_id = f"p{source_page_index}|{attachment.id}"
            rendered_block = RenderedTextBlock(
                id=block_id,
                source_page_index=source_page_index,
                source_attachment_id=attachment.id,
                text=attachment.text,
                role=attachment.role,
                bbox=bbox,
                font_size=font_size,
                anchor=attachment.anchor,
            )
            rendered[page_index].append(rendered_block)
            text_blocks[page_index].append(
                TextBlock(
                    text=attachment.text,
                    bbox=(bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height),
                    role=attachment.role,
                    font_size=font_size,
                )
            )

    return TextPlacementResult(dict(text_blocks), dict(rendered))


def _source_anchor_target(
    source_page_index: int,
    attachment: SourceTextAttachment,
    anchor_lookup: dict[str, tuple[int, BoundingBox]],
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
) -> tuple[int, BoundingBox]:
    source_id = attachment.anchor.source_id
    if source_id:
        for candidate in (f"p{source_page_index}|{source_id}", source_id):
            target = anchor_lookup.get(candidate)
            if target is not None:
                return target
    page_index = _relative_render_page(
        source_page_index,
        attachment.anchor.relative_y,
        measure_ranges_by_page,
    )
    relative_y = attachment.anchor.relative_y
    if relative_y is None:
        relative_y = 0.5
    return page_index, BoundingBox(
        x=_A4_WIDTH / 2,
        y=_SAFE_TOP + relative_y * (_A4_HEIGHT - _SAFE_TOP - _SAFE_BOTTOM),
        width=1,
        height=1,
    )


def _relative_render_page(
    source_page_index: int,
    relative_y: float | None,
    measure_ranges_by_page: list[list[RenderPageMeasureRange]],
) -> int:
    matches = [
        (page_index, item)
        for page_index, ranges in enumerate(measure_ranges_by_page)
        for item in ranges
        if item.source_page_index == source_page_index
    ]
    if not matches:
        if not measure_ranges_by_page:
            return 0
        return min(source_page_index, len(measure_ranges_by_page) - 1)

    ratio = max(0.0, min(1.0, relative_y if relative_y is not None else 0.5))
    numbered = [
        (page_index, item)
        for page_index, item in matches
        if item.start_measure_number is not None and item.end_measure_number is not None
    ]
    if numbered:
        start = min(item.start_measure_number for _, item in numbered)
        end = max(item.end_measure_number for _, item in numbered)
        target = start + round((end - start) * ratio)
        for page_index, item in numbered:
            if item.start_measure_number <= target <= item.end_measure_number:
                return page_index
    unique_pages = list(dict.fromkeys(page_index for page_index, _ in matches))
    target_index = min(len(unique_pages) - 1, round((len(unique_pages) - 1) * ratio))
    return unique_pages[target_index]


def _render_anchor_lookup(layout_svgs: list[str]) -> dict[str, tuple[int, BoundingBox]]:
    lookup: dict[str, tuple[int, BoundingBox]] = {}
    for page_index, svg in enumerate(layout_svgs):
        try:
            root = ET.fromstring(svg)
        except ET.ParseError:
            continue
        for element in root.iter():
            bbox = _data_bbox(element.get("data-bbox"))
            if bbox is None:
                continue
            for source_id in (element.get("data-source-ids") or "").split():
                if source_id:
                    lookup[source_id] = (page_index, bbox)
    return lookup


def _data_bbox(value: str | None) -> BoundingBox | None:
    if not value:
        return None
    try:
        x, y, width, height = (float(part) for part in value.split())
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return BoundingBox(x=x, y=y, width=width, height=height)


def _render_bbox(
    attachment: SourceTextAttachment,
    anchor: BoundingBox,
    width: float,
    font_size: float,
    placement: str,
    lane: int,
) -> BoundingBox:
    center_x = anchor.x + anchor.width / 2
    x = center_x - width / 2 + attachment.anchor.offset_x
    if placement == "below":
        y = anchor.y + anchor.height + 24 + lane * (font_size + 8)
    elif placement == "above":
        y = anchor.y - font_size - 24 - lane * (font_size + 8)
    else:
        y = anchor.y + lane * (font_size + 8)
    y += attachment.anchor.offset_y
    x = max(_SAFE_X, min(_A4_WIDTH - _SAFE_X - width, x))
    y = max(_SAFE_TOP, min(_A4_HEIGHT - _SAFE_BOTTOM - font_size * 1.35, y))
    return BoundingBox(x=x, y=y, width=width, height=font_size * 1.35)


def _placement(role: str) -> str:
    if role == "lyric":
        return "below"
    if role in {"expression", "other"}:
        return "above"
    return "fixed"


def _font_size(value: float | None) -> float:
    if value is None:
        return 20.0
    return max(8.0, min(36.0, float(value)))


def _text_width(attachment: SourceTextAttachment, font_size: float) -> float:
    estimated = max(80.0, len(attachment.text) * font_size * 0.8)
    return min(_A4_WIDTH - _SAFE_X * 2, estimated)
