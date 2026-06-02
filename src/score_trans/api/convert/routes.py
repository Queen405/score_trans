from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_convert_actions
from ...exec.convert.actions import ConvertActions
from ...models.convert.schemas import (
    JianpuToMusicXmlRequest,
    JianpuToMusicXmlResponse,
    MusicXmlToJianpuRequest,
    MusicXmlToJianpuResponse,
)

router = APIRouter(prefix="/convert", tags=["convert"])


@router.post("/musicxml-to-jianpu", response_model=MusicXmlToJianpuResponse)
async def musicxml_to_jianpu(
    req: MusicXmlToJianpuRequest,
    actions: ConvertActions = Depends(get_convert_actions),
):
    return actions.musicxml_to_jianpu_response(req)


@router.post("/jianpu-to-musicxml", response_model=JianpuToMusicXmlResponse)
async def jianpu_to_musicxml(
    req: JianpuToMusicXmlRequest,
    actions: ConvertActions = Depends(get_convert_actions),
):
    return actions.jianpu_to_musicxml_response(req)

