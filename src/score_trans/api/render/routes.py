from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_render_actions
from ...exec.render.actions import RenderActions
from ...models.render.schemas import (
    FinalRenderRequest,
    FinalRenderResponse,
    NormalizeJianpuTextRequest,
    NormalizeJianpuTextResponse,
    PreservingLayoutRequest,
    PreservingLayoutResponse,
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
    RenderJianpuTextSvgRequest,
    RenderJianpuTextSvgResponse,
)

router = APIRouter(prefix="/render", tags=["render"])


@router.post("/jianpu-svg", response_model=RenderJianpuSvgResponse)
async def render_jianpu_svg(
    req: RenderJianpuSvgRequest,
    actions: RenderActions = Depends(get_render_actions),
):
    return actions.render_jianpu_svg(req)


@router.post("/jianpu-text-svg", response_model=RenderJianpuTextSvgResponse)
async def render_jianpu_text_svg(
    req: RenderJianpuTextSvgRequest,
    actions: RenderActions = Depends(get_render_actions),
):
    return actions.render_jianpu_text_svg(req)


@router.post("/normalize-jianpu-text", response_model=NormalizeJianpuTextResponse)
async def normalize_jianpu_text_route(
    req: NormalizeJianpuTextRequest,
    actions: RenderActions = Depends(get_render_actions),
):
    return actions.normalize_jianpu_text(req)


@router.post("/preserving-layout", response_model=PreservingLayoutResponse)
async def render_preserving_layout(
    req: PreservingLayoutRequest,
    actions: RenderActions = Depends(get_render_actions),
):
    return actions.render_preserving_layout(req)


@router.post("/final-output", response_model=FinalRenderResponse)
async def render_final_output(
    req: FinalRenderRequest,
    actions: RenderActions = Depends(get_render_actions),
):
    return actions.render_final_output(req)

