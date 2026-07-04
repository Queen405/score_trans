from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from ..dependencies import get_settings_actions
from ...exec.settings.actions import SettingsActions
from ...models.settings.schemas import (
    CacheCleanupResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    ocr_provider: str | None = None,
    ai_provider: str | None = None,
    assistant_provider: str | None = None,
    actions: SettingsActions = Depends(get_settings_actions),
):
    return await asyncio.to_thread(
        actions.get_settings,
        ocr_provider=ocr_provider,
        ai_provider=ai_provider,
        assistant_provider=assistant_provider,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    actions: SettingsActions = Depends(get_settings_actions),
):
    return await asyncio.to_thread(actions.update_settings, req)


@router.delete("/cache", response_model=CacheCleanupResponse)
async def clear_cache(
    actions: SettingsActions = Depends(get_settings_actions),
):
    return await asyncio.to_thread(actions.clear_cache)
