from __future__ import annotations

import json
import re
from typing import Any

from ...models.common.errors import OCRError
from ...models.score import OCRTextBlock, TextRole
from ...utils.bbox import coerce_bbox
from ...utils.dict_tools import first_present
from ...utils.json_parsing import content_to_text, parse_json_content
from ...utils.text import cleaned_plain_text_lines
from .text import infer_text_role, normalize_text_role
from .utils import _font_size_from_raw


def plain_text_to_blocks(text: str) -> list[OCRTextBlock]:
    return [
        OCRTextBlock(text=line, role=infer_text_role(line))
        for line in cleaned_plain_text_lines(text)
    ]


def parse_openai_compatible_response(response: dict[str, Any]) -> list[OCRTextBlock]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OCRError("OCR provider response did not contain message content.") from exc

    try:
        payload = parse_json_content(content)
    except (json.JSONDecodeError, OCRError):
        return plain_text_to_blocks(content_to_text(content))

    if isinstance(payload, list):
        return coerce_text_block_list(payload)
    if isinstance(payload, str):
        return plain_text_to_blocks(payload)
    if not isinstance(payload, dict):
        raise OCRError("OCR provider JSON response must be an object or list.")

    raw_blocks = find_text_blocks_payload(payload)
    if raw_blocks is None:
        text = text_from_payload(payload)
        if text:
            return plain_text_to_blocks(text)
        raise OCRError("OCR provider JSON must contain a text block list.")
    if not isinstance(raw_blocks, list):
        raise OCRError("OCR provider JSON must contain a text_blocks list.")
    return coerce_text_block_list(raw_blocks)


def coerce_text_block_list(raw_blocks: list[Any]) -> list[OCRTextBlock]:
    blocks: list[OCRTextBlock] = []
    for raw in raw_blocks:
        if isinstance(raw, dict):
            blocks.append(coerce_text_block(raw))
        elif raw is not None and str(raw).strip():
            blocks.append(OCRTextBlock(text=str(raw).strip(), role=infer_text_role(str(raw))))
    return blocks


def find_text_blocks_payload(payload: dict[str, Any]) -> list[Any] | None:
    for key in ("text_blocks", "blocks", "items", "texts", "detections", "results", "lines", "words"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = find_text_blocks_payload(value)
            if nested is not None:
                return nested

    for key in ("data", "result", "output", "ocr"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = find_text_blocks_payload(value)
            if nested is not None:
                return nested

    if text_from_raw_block(payload):
        return [payload]

    return None


def text_from_payload(payload: dict[str, Any]) -> str:
    for key in ("text", "content", "markdown", "data", "result", "output", "ocr"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def text_from_raw_block(raw: dict[str, Any]) -> str:
    for key in ("text", "content", "value", "label", "transcription", "markdown"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if value is not None and not isinstance(value, (dict, list)):
            text = str(value).strip()
            if text:
                return text
    return ""


def coerce_text_block(raw: Any) -> OCRTextBlock:
    if not isinstance(raw, dict):
        raise OCRError("Each OCR text block must be an object.")

    text = text_from_raw_block(raw)
    bbox = coerce_bbox(
        first_present(
            raw,
            (
                "bbox",
                "bbox_2d",
                "box",
                "bounding_box",
                "boundingBox",
                "position",
                "rect",
                "coordinates",
                "points",
            ),
        )
    )
    confidence = raw.get("confidence")
    if confidence is not None:
        confidence = float(confidence)

    role = normalize_text_role(raw.get("role") or raw.get("type") or raw.get("category"), text)
    if role not in TextRole.__args__:
        role = infer_text_role(text)

    return OCRTextBlock(
        text=text,
        bbox=bbox,
        confidence=confidence,
        role=role,
        font_size=_font_size_from_raw(raw),
        measure_number=raw.get("measure_number") or raw.get("measure"),
    )
