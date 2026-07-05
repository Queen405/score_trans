from __future__ import annotations

from typing import Any, Callable

from .protocols import ChatProvider, VisionJianpuProvider

_PROVIDER_REGISTRY: dict[str, Callable[..., VisionJianpuProvider]] = {}


def register_provider(
    name: str,
    factory: Callable[..., VisionJianpuProvider],
) -> None:
    """Register a provider factory under a canonical name."""
    _PROVIDER_REGISTRY[name] = factory


def create_provider(name: str | None = None, **kwargs: Any) -> VisionJianpuProvider:
    """Instantiate a registered provider by name.

    Defaults to ``openai_compatible`` when *name* is None or empty.
    """
    resolved = (name or "openai_compatible").strip().lower()
    if resolved not in _PROVIDER_REGISTRY:
        available = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown AI provider '{name}'. Available: {available or 'none'}"
        )
    return _PROVIDER_REGISTRY[resolved](**kwargs)


def available_providers() -> list[str]:
    """Return the list of registered provider names."""
    return sorted(_PROVIDER_REGISTRY)


_CHAT_PROVIDER_REGISTRY: dict[str, Callable[..., ChatProvider]] = {}


def register_chat_provider(
    name: str,
    factory: Callable[..., ChatProvider],
) -> None:
    """Register a chat provider factory under a canonical name."""
    _CHAT_PROVIDER_REGISTRY[name] = factory


def create_chat_provider(name: str | None = None, **kwargs: Any) -> ChatProvider:
    """Instantiate a registered chat provider by name.

    Defaults to ``openai_compatible`` when *name* is None or empty.
    """
    resolved = (name or "openai_compatible").strip().lower()
    if resolved not in _CHAT_PROVIDER_REGISTRY:
        available = ", ".join(sorted(_CHAT_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown chat provider '{name}'. Available: {available or 'none'}"
        )
    return _CHAT_PROVIDER_REGISTRY[resolved](**kwargs)


def available_chat_providers() -> list[str]:
    """Return the list of registered chat provider names."""
    return sorted(_CHAT_PROVIDER_REGISTRY)
