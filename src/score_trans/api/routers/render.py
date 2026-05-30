from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_config, get_render_jianpu, get_render_text, get_upload_manager
from ..schemas import (
    PreservingLayoutRequest,
    PreservingLayoutResponse,
    RenderJianpuSvgRequest,
    RenderJianpuSvgResponse,
    RenderJianpuTextSvgRequest,
    RenderJianpuTextSvgResponse,
)
from ..uploads import UploadManager
from ...services.settings import ToolConfig
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

    import uuid
    svg_name = f"{uuid.uuid4().hex[:12]}.svg"
    svg_path = uploads.base_dir / svg_name

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
        import uuid
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

    import uuid
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
    musicxml_path = uploads.get_path(req.musicxml_file_id)
    if not musicxml_path or not musicxml_path.exists():
        raise HTTPException(404, f"MusicXML 文件不存在：{req.musicxml_file_id}")

    image_path = uploads.get_path(req.page_image_file_id)
    if not image_path or not image_path.exists():
        raise HTTPException(404, f"页面图片不存在：{req.page_image_file_id}")

    # Build the score with OCR overlay
    score = uc.build_score(
        musicxml_path,
        target_key=req.target_key,
        start_measure_number=req.start_measure_number,
        image_path=image_path,
    )

    # Render the SVG using the existing rendering service
    import uuid
    from ...services.rendering import render_score_svg, RenderOptions

    svg_name = f"{uuid.uuid4().hex[:12]}.svg"
    svg_path = uploads.base_dir / svg_name

    options = RenderOptions(title=score.title)
    svg_content = render_score_svg(score, options)
    svg_path.write_text(svg_content, encoding="utf-8")

    svg_id = uploads.register(svg_path)

    # Try to get page dimensions from the image
    page_width = 1600.0
    page_height = 1200.0
    try:
        from ...services.ocr_provider import OpenAICompatibleOCRProvider
        provider = OpenAICompatibleOCRProvider()
        # Read image dimensions if possible
        import struct
        with open(image_path, "rb") as f:
            head = f.read(24)
            if len(head) >= 24 and head.startswith(b'\x89PNG'):
                page_width = float(struct.unpack(">I", head[16:20])[0])
                page_height = float(struct.unpack(">I", head[20:24])[0])
    except Exception:
        pass

    return PreservingLayoutResponse(
        svg_file_id=svg_id,
        page_width=page_width,
        page_height=page_height,
    )
