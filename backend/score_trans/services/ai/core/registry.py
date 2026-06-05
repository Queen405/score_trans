from __future__ import annotations

from typing import Any, Callable

from .protocols import VisionJianpuProvider

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
            f"Unknown AI provider '{name}'. "
            f"Available: {available or 'none'}"
        )
    return _PROVIDER_REGISTRY[resolved](**kwargs)


def available_providers() -> list[str]:
    """Return the list of registered provider names."""
    return sorted(_PROVIDER_REGISTRY)
