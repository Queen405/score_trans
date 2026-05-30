from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_render_jianpu, get_render_text, get_upload_manager
from ..schemas import (
    FinalRenderRequest,
    FinalRenderResponse,
    PreservingLayoutRequest,
    PreservingLayoutResponse,
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
    RenderJianpuTextSvgRequest,
    RenderJianpuTextSvgResponse,
)
from ..uploads import UploadManager
from ...services.image_info import image_dimensions
from ...use_cases import RenderJianpuTextUseCase, RenderMusicXmlJianpuUseCase

router = APIRouter(prefix="/render", tags=["render"])


@router.post("/jianpu-svg", response_model=RenderJianpuSvgResponse)
async def render_jianpu_svg(
    req: RenderJianpuSvgRequest,
    uc: RenderMusicXmlJianpuUseCase = Depends(get_render_jianpu),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Render a MusicXML file as a Jianpu SVG."""
    path = uploads.get_path(req.musicxml_file_id)
    if not path or not path.exists():
        raise HTTPException(404, f"文件不存在：{req.musicxml_file_id}")

    svg_name = f"{uuid.uuid4().hex[:12]}.svg"
    svg_path = uploads.base_dir / svg_name

    if req.page_image_file_id:
        image_path = uploads.get_path(req.page_image_file_id)
        if not image_path or not image_path.exists():
            raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")
        page_width, page_height = image_dimensions(image_path)
        uc.execute_page(
            path,
            svg_path,
            page_width=page_width,
            page_height=page_height,
            target_key=req.target_key,
            start_measure_number=req.start_measure_number,
            image_path=image_path,
            title=req.title,
        )
    else:
        uc.execute(
            path,
            svg_path,
            target_key=req.target_key,
            start_measure_number=req.start_measure_number,
            title=req.title,
        )

    svg_id = uploads.register(svg_path)
    return RenderJianpuSvgResponse(svg_file_id=svg_id)


@router.post("/jianpu-text-svg", response_model=RenderJianpuTextSvgResponse)
async def render_jianpu_text_svg(
    req: RenderJianpuTextSvgRequest,
    uc: RenderJianpuTextUseCase = Depends(get_render_text),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Render Jianpu text as an SVG."""
    if req.jianpu_text:
        txt_name = f"{uuid.uuid4().hex[:12]}.txt"
        txt_path = uploads.base_dir / txt_name
        txt_path.write_text(req.jianpu_text, encoding="utf-8")
        input_path = txt_path
    elif req.jianpu_file_id:
        input_path = uploads.get_path(req.jianpu_file_id)
        if not input_path or not input_path.exists():
            raise HTTPException(404, f"文件不存在：{req.jianpu_file_id}")
    else:
        raise HTTPException(400, "必须提供 jianpu_text 或 jianpu_file_id")

    svg_name = f"{uuid.uuid4().hex[:12]}.svg"
    svg_path = uploads.base_dir / svg_name

    uc.execute(input_path, svg_path, title=req.title)

    svg_id = uploads.register(svg_path)
    return RenderJianpuTextSvgResponse(svg_file_id=svg_id)


@router.post("/preserving-layout", response_model=PreservingLayoutResponse)
async def render_preserving_layout(
    req: PreservingLayoutRequest,
    uc: RenderMusicXmlJianpuUseCase = Depends(get_render_jianpu),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Render MusicXML to Jianpu SVG with OCR text overlay, preserving original page layout."""
    response = await _render_final_page(req, uc, uploads, require_page_image=True)
    return PreservingLayoutResponse(**response.model_dump())


@router.post("/final-output", response_model=FinalRenderResponse)
async def render_final_output(
    req: FinalRenderRequest,
    uc: RenderMusicXmlJianpuUseCase = Depends(get_render_jianpu),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Render the final Jianpu page with OMR conversion and OCR annotations in one pass."""
    return await _render_final_page(req, uc, uploads, require_page_image=False)


async def _render_final_page(
    req: FinalRenderRequest | PreservingLayoutRequest,
    uc: RenderMusicXmlJianpuUseCase,
    uploads: UploadManager,
    *,
    require_page_image: bool,
) -> FinalRenderResponse:
    musicxml_path = uploads.get_path(req.musicxml_file_id)
    if not musicxml_path or not musicxml_path.exists():
        raise HTTPException(404, f"MusicXML 文件不存在：{req.musicxml_file_id}")

    image_path = None
    page_width = 1600.0
    page_height = 1200.0
    if req.page_image_file_id:
        image_path = uploads.get_path(req.page_image_file_id)
        if not image_path or not image_path.exists():
            raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")
        page_width, page_height = image_dimensions(image_path)
    elif require_page_image:
        raise HTTPException(400, "必须提供 page_image_file_id")

    svg_name = f"{uuid.uuid4().hex[:12]}.svg"
    svg_path = uploads.base_dir / svg_name
    uc.execute_page(
        musicxml_path,
        svg_path,
        page_width=page_width,
        page_height=page_height,
        target_key=req.target_key,
        start_measure_number=req.start_measure_number,
        image_path=image_path,
        title=req.title,
    )
    svg_id = uploads.register(svg_path)
    return FinalRenderResponse(
        svg_file_id=svg_id,
        page_width=page_width,
        page_height=page_height,
    )
