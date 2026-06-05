# noqa: D100
from __future__ import annotations

# Compatibility re-export for legacy imports.
# New code should import from score_trans.services.ai.core.
from .core.registry import _PROVIDER_REGISTRY, available_providers, create_provider, register_provider

__all__ = ["register_provider", "create_provider", "available_providers", "_PROVIDER_REGISTRY"]
