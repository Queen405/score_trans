"""Shared httpx-based OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from ....utils.openai_response import (
    completion_content,
    completion_finish_reason,
    stream_delta,
    stream_finish_reason,
)


@dataclass(slots=True)
class CompletionResult:
    """Non-stream completion content plus the provider finish metadata.

    Internal to the AI provider layer: callers that only need text use
    ``result.content``; continuation logic additionally inspects
    ``finish_reason`` ("stop", "length", or None when the provider omits it).
    """

    content: str
    finish_reason: str | None = None


@dataclass(slots=True)
class StreamChunk:
    """One streamed text piece, or a final marker carrying finish_reason.

    A trailing chunk with empty ``text`` and non-None ``finish_reason`` is
    emitted once per stream so consumers can detect truncation ("length").
    """

    text: str
    finish_reason: str | None = None


def chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    timeout: float = 120.0,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
    extra_body: dict[str, Any] | None = None,
) -> CompletionResult:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint.

    Returns the content of the first choice plus its finish_reason.
    """
    url = f"{base_url}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if response_format is not None:
        body["response_format"] = response_format
    if extra_body:
        body.update(extra_body)

    resp = httpx.post(
        url,
        json=body,
        headers=headers,
        timeout=httpx.Timeout(connect=30, read=timeout, write=timeout, pool=30),
    )
    resp.raise_for_status()
    data = resp.json()
    return CompletionResult(
        content=completion_content(data, provider_name="AI"),
        finish_reason=completion_finish_reason(data, provider_name="AI"),
    )


def chat_completion_chunks(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float = 0.3,
    timeout: float = 120.0,
    max_tokens: int | None = None,
    extra_body: dict[str, Any] | None = None,
) -> Iterator[StreamChunk]:
    """Stream text chunks from an OpenAI-compatible ``/chat/completions`` endpoint.

    Yields one StreamChunk per text piece; a final chunk with empty text
    carries the last seen finish_reason (None when the provider omits it).
    """
    url = f"{base_url}/chat/completions"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if extra_body:
        body.update(extra_body)

    in_reasoning = False
    last_finish_reason: str | None = None
    with httpx.stream("POST", url, json=body, headers=headers, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            finish_reason = stream_finish_reason(data, provider_name="AI")
            if finish_reason is not None:
                last_finish_reason = finish_reason
            delta = stream_delta(data, provider_name="AI")
            if delta is None:
                continue
            reasoning = delta.get("reasoning_content")
            if reasoning:
                if not in_reasoning:
                    in_reasoning = True
                    yield StreamChunk("<think>")
                yield StreamChunk(reasoning)
            content = delta.get("content")
            if content:
                if in_reasoning:
                    in_reasoning = False
                    yield StreamChunk("</think>\n\n")
                yield StreamChunk(content)

    if in_reasoning:
        yield StreamChunk("</think>\n\n")
    yield StreamChunk("", finish_reason=last_finish_reason)
