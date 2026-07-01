"""Shared httpx-based OpenAI-compatible chat completions client for OCR."""

from __future__ import annotations

from typing import Any

import httpx


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
) -> str:
    """Call an OpenAI-compatible ``/chat/completions`` endpoint."""
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

    resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]
