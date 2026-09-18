from __future__ import annotations

import json
import math
import re
from typing import Any

_FIELD_DEFAULTS: dict[str, Any] = {
    "schema_version": 1,
    "unresolved_candidates": [],
    "row_type": "notation",
    "key": None,
    "meter": None,
    "tempo": None,
    "title": None,
    "row_text": "",
    "tokens": [],
    "warnings": [],
    "confidence": None,
}

_VALID_ROW_TYPES = {"header", "notation", "lyrics", "other"}


def parse_row_response(content: str) -> dict[str, Any]:
    warnings: list[str] = []
    data = _try_parse(content)
    if data is None:
        data = {}
        warnings.append("JSON 解析失败，已降级为空结果")
    if not isinstance(data, dict):
        data = {}
        warnings.append("JSON 响应不是对象，已降级为空结果")

    result: dict[str, Any] = {}
    for field_name, default in _FIELD_DEFAULTS.items():
        value = data.get(field_name, default)
        if value is None and default is not None:
            value = default
        result[field_name] = value

    if result["row_type"] not in _VALID_ROW_TYPES:
        result["row_type"] = "notation"
    if not isinstance(result["row_text"], str):
        result["row_text"] = str(result["row_text"])
    if not isinstance(result["warnings"], list):
        result["warnings"] = []
    if result["confidence"] is not None:
        try:
            confidence = _to_float(result["confidence"])
            result["confidence"] = (
                min(1.0, max(0.0, confidence)) if confidence is not None else None
            )
        except (TypeError, ValueError):
            result["confidence"] = None

    result["tokens"] = _normalize_tokens(
        data.get("tokens"), warnings, data.get("schema_version") == 2
    )
    version = data.get("schema_version", 1)
    if type(version) is not int or version not in (1, 2):
        warnings.append("不支持的响应协议版本，禁止定位")
        result["schema_version"] = 2
        for token in result["tokens"]:
            token["candidate_ids"] = ()
    unresolved = result["unresolved_candidates"]
    if not isinstance(unresolved, list):
        unresolved = [{"reason": "unresolved_candidates 格式错误"}]
    result["unresolved_candidates"] = [
        item if isinstance(item, dict) else {"reason": str(item)} for item in unresolved
    ]
    if unresolved:
        warnings.append("本行存在未识别候选，转写不完整")
    missing = [f for f in ("row_text", "tokens") if f not in data]
    if missing:
        warnings.append(f"JSON 响应缺少字段: {', '.join(missing)}")
    result["warnings"] = [*warnings, *[str(w) for w in result["warnings"]]]
    return result


def _try_parse(content: str) -> Any | None:
    text = content.strip()
    if not text:
        return None
    text = _strip_markdown_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    extracted = _extract_json_object(text)
    if extracted is not None:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass
        repaired = _repair_truncated(extracted)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
    return None


def _strip_markdown_fence(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    end = text.rfind("}")
    if end > start:
        return text[start : end + 1]
    return text[start:]


def _repair_truncated(text: str) -> str:
    repaired = text.rstrip()
    if repaired.count('"') % 2 == 1:
        repaired += '"'
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in repaired:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    closers = {"{": "}", "[": "]"}
    while stack:
        repaired += closers[stack.pop()]
    return repaired


def _normalize_tokens(
    raw_tokens: Any, warnings: list[str], numbered: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(raw_tokens, list):
        if raw_tokens is not None:
            warnings.append("tokens 字段不是数组，已忽略")
        return []
    tokens: list[dict[str, Any]] = []
    for item in raw_tokens:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text:
            continue
        tokens.append(
            {
                "text": text,
                "x": _to_float(item.get("x")),
                "w": _to_float(item.get("w")),
                "role": str(item.get("role") or "other"),
                "y": _to_float(item.get("y")),
                "h": _to_float(item.get("h")),
                "candidate_ids": tuple(item["candidate_ids"])
                if isinstance(item.get("candidate_ids"), list)
                and all(isinstance(cid, str) for cid in item["candidate_ids"])
                else (),
            }
        )

    for token in tokens:
        x, w = token["x"], token["w"]
        if (
            not numbered
            and not token["candidate_ids"]
            and (x is None or w is None or not 0 <= x < 1 or w <= 0 or x + w > 1 + 1e-9)
        ):
            warnings.append(f"token {token['text']}: 历史坐标缺失或无效，未补位/裁剪")
    return tokens


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None
