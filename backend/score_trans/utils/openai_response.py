from __future__ import annotations

from typing import Any


def completion_content(data: Any, *, provider_name: str) -> str:
    choices = _choices(data, provider_name=provider_name, allow_empty=False)
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError(f"{provider_name} provider response choice is missing message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError(
            f"{provider_name} provider response message is missing text content"
        )
    return content


def completion_finish_reason(data: Any, *, provider_name: str) -> str | None:
    """Return finish_reason of the first non-stream choice, if present."""
    choices = _choices(data, provider_name=provider_name, allow_empty=False)
    finish_reason = choices[0].get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def stream_finish_reason(data: Any, *, provider_name: str) -> str | None:
    """Return finish_reason of the first stream choice, if present."""
    choices = _choices(data, provider_name=provider_name, allow_empty=True)
    if not choices:
        return None
    finish_reason = choices[0].get("finish_reason")
    return finish_reason if isinstance(finish_reason, str) else None


def stream_delta(data: Any, *, provider_name: str) -> dict[str, Any] | None:
    choices = _choices(data, provider_name=provider_name, allow_empty=True)
    if not choices:
        return None
    delta = choices[0].get("delta")
    if delta is None:
        return None
    if not isinstance(delta, dict):
        raise ValueError(f"{provider_name} provider stream choice has invalid delta")
    return delta


def _choices(
    data: Any,
    *,
    provider_name: str,
    allow_empty: bool,
) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError(f"{provider_name} provider response must be a JSON object")
    error = data.get("error")
    if error:
        if isinstance(error, dict):
            detail = error.get("message") or error.get("code") or str(error)
        else:
            detail = str(error)
        raise RuntimeError(f"{provider_name} provider returned an error: {detail}")

    choices = data.get("choices")
    if choices is None and allow_empty:
        return []
    if not isinstance(choices, list) or (not choices and not allow_empty):
        raise ValueError(
            f"{provider_name} provider response must contain a non-empty choices list"
        )
    if not choices:
        return []
    if not isinstance(choices[0], dict):
        raise ValueError(f"{provider_name} provider response has an invalid choice")
    return choices
