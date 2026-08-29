from __future__ import annotations

import logging

from ...models.jianpu.types import RekeyResult
from ...services.jianpu.rekey_service import RekeyService

logger = logging.getLogger(__name__)


class JianpuActions:
    """简谱相关的执行动作。"""

    def __init__(self, rekey: RekeyService | None = None) -> None:
        self._rekey = rekey

    def _rekey_service(self) -> RekeyService:
        if self._rekey is None:
            from ..composition import shared_rekey_service

            self._rekey = shared_rekey_service()
        return self._rekey

    async def rekey_text(self, text: str, previous_text: str) -> RekeyResult:
        """根据之前的简谱文本对当前文本转调以保持音高不变。"""
        return await self._rekey_service().rekey_text(text, previous_text)
