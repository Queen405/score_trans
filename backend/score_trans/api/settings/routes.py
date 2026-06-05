from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_settings_actions
from ...exec.settings.actions import SettingsActions
from ...models.settings.schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(actions: SettingsActions = Depends(get_settings_actions)):
    return actions.get_settings()


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    actions: SettingsActions = Depends(get_settings_actions),
):
    return actions.update_settings(req)

