from __future__ import annotations

from typing import Final


class UnsetType:
    __slots__ = ()


UNSET: Final = UnsetType()
