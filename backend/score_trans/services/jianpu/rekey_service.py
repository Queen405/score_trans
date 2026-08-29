from __future__ import annotations

import asyncio
import logging

from ...domain.accidentals import normalize_accidental_mode
from ...domain.rekey import rekey_text as domain_rekey_text
from ...models.common.types import AccidentalMode
from ...models.jianpu.types import RekeyResult
from ..settings.settings_service import SettingsService

logger = logging.getLogger(__name__)


class RekeyService:
    """简谱转调编排服务：从设置读取变音记号模式，委托 domain 层做纯计算。"""

    def __init__(self, settings: SettingsService | None = None) -> None:
        self._settings = settings

    def _effective_accidental_mode(self) -> AccidentalMode:
        if self._settings is None:
            return "auto"
        try:
            value = self._settings.get_all().get("accidental_mode", "")
        except Exception:
            logger.warning("读取 accidental_mode 设置失败，回退 auto")
            return "auto"
        return normalize_accidental_mode(value)

    async def rekey_text(self, text: str, previous_text: str) -> RekeyResult:
        # 设置读取会命中 SQLite，与转调一起放到线程里，避免阻塞事件循环。
        return await asyncio.to_thread(self._rekey_blocking, text, previous_text)

    def _rekey_blocking(self, text: str, previous_text: str) -> RekeyResult:
        return domain_rekey_text(
            text,
            previous_text,
            accidental_mode=self._effective_accidental_mode(),
        )
