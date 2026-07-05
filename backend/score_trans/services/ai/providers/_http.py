"""Shared httpx-based OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from ....utils.openai_response import completion_content, stream_delta


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
) -> str:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint.

    Returns the content string from the first choice.
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
        url, json=body, headers=headers,
        timeout=httpx.Timeout(connect=30, read=timeout, write=timeout, pool=30),
    )
    resp.raise_for_status()
    data = resp.json()
    return completion_content(data, provider_name="AI")


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
) -> Iterator[str]:
    """Stream text chunks from an OpenAI-compatible ``/chat/completions`` endpoint."""
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
            delta = stream_delta(data, provider_name="AI")
            if delta is None:
                continue
            reasoning = delta.get("reasoning_content")
            if reasoning:
                if not in_reasoning:
                    in_reasoning = True
                    yield "<think>"
                yield reasoning
            content = delta.get("content")
            if content:
                if in_reasoning:
                    in_reasoning = False
                    yield "</think>\n\n"
                yield content

    if in_reasoning:
        yield "</think>\n\n"
