from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ...domain.rekey import rekey_text as domain_rekey_text
from ...models.common.types import AccidentalMode
from ..dependencies import get_settings_dao
from ...dao.settings.settings_dao import SettingsDao

if TYPE_CHECKING:
    from fastapi.requests import Request

logger = logging.getLogger(__name__)


class JianpuActions:
    """简谱相关的执行动作。"""
    
    def __init__(self):
        self._settings_dao: SettingsDao | None = None
    
    async def initialize(self) -> None:
        """初始化 action（从依赖注入获取 settings）。"""
        # Lazy load settings DAO
        pass
    
    def _get_settings_dao(self) -> SettingsDao:
        if self._settings_dao is None:
            self._settings_dao = get_settings_dao()
        return self._settings_dao
    
    async def rekey_text(
        self,
        text: str,
        previous_text: str,
        *,
        accidental_mode: AccidentalMode | None = None,
    ) -> str:
        """根据之前的文本对当前文本进行转调。
        
        Args:
            text: 当前简谱文本（可能包含新的调号）
            previous_text: 之前的简谱文本（用于获取旧调号信息）
            accidental_mode: 变音记号模式（auto/sharp/flat），从 settings 读取
        
        Returns:
            转调后的文本
        """
        # 从 settings 读取 accidental_mode
        try:
            settings_dao = self._get_settings_dao()
            mode_value = settings_dao.get("accidental_mode")
            effective_mode: AccidentalMode = (
                AccidentalMode(mode_value) if mode_value else "auto"
            )
        except Exception:
            effective_mode = "auto"
        
        # 在子线程中执行计算密集型操作，避免阻塞事件循环
        result = await asyncio.to_thread(
            lambda: domain_rekey_text(
                text,
                previous_text,
                accidental_mode=effective_mode,
            )
        )
        
        return result
