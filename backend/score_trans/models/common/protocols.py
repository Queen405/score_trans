from __future__ import annotations

from typing import BinaryIO, Protocol


class UploadFileLike(Protocol):
    filename: str | None
    file: BinaryIO

    async def read(self, size: int = -1) -> bytes: ...
