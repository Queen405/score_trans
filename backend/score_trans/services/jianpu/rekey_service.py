from __future__ import annotations

import asyncio
import logging
from typing import cast

from ...domain.rekey import rekey_text as domain_rekey_text
from ...models.common.types import AccidentalMode
from ..settings.settings_service import SettingsService

logger = logging.getLogger(__name__)

_VALID_ACCIDENTAL_MODES: frozenset[str] = frozenset({"auto", "sharp", "flat"})


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
        if value in _VALID_ACCIDENTAL_MODES:
            return cast(AccidentalMode, value)
        return "auto"

    async def rekey_text(self, text: str, previous_text: str) -> str:
        accidental_mode = self._effective_accidental_mode()
        return await asyncio.to_thread(
            lambda: domain_rekey_text(
                text,
                previous_text,
                accidental_mode=accidental_mode,
            )
        )
