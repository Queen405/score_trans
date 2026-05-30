from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_convert_to_jianpu, get_convert_to_musicxml, get_upload_manager
from ..schemas import (
    JianpuToMusicXmlRequest,
    JianpuToMusicXmlResponse,
    MusicXmlToJianpuRequest,
    MusicXmlToJianpuResponse,
)
from ..uploads import UploadManager
from ...use_cases import ConvertJianpuToMusicXmlUseCase, ConvertMusicXmlToJianpuUseCase
from ...services.file_service import FileService

router = APIRouter(prefix="/convert", tags=["convert"])


@router.post("/musicxml-to-jianpu", response_model=MusicXmlToJianpuResponse)
async def musicxml_to_jianpu(
    req: MusicXmlToJianpuRequest,
    uc: ConvertMusicXmlToJianpuUseCase = Depends(get_convert_to_jianpu),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Convert a MusicXML file to Jianpu text."""
    path = uploads.get_path(req.musicxml_file_id)
    if not path or not path.exists():
        raise HTTPException(404, f"文件不存在：{req.musicxml_file_id}")

    jianpu_text = uc.execute(
        path,
        target_key=req.target_key,
        start_measure_number=req.start_measure_number,
    )
    return MusicXmlToJianpuResponse(jianpu_text=jianpu_text)


@router.post("/jianpu-to-musicxml", response_model=JianpuToMusicXmlResponse)
async def jianpu_to_musicxml(
    req: JianpuToMusicXmlRequest,
    uc: ConvertJianpuToMusicXmlUseCase = Depends(get_convert_to_musicxml),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Convert Jianpu text to MusicXML."""
    if req.jianpu_text:
        xml_text = uc.execute_text(req.jianpu_text, title=req.title)
    elif req.jianpu_file_id:
        path = uploads.get_path(req.jianpu_file_id)
        if not path or not path.exists():
            raise HTTPException(404, f"文件不存在：{req.jianpu_file_id}")
        xml_text = uc.execute_file(path, title=req.title)
    else:
        raise HTTPException(400, "必须提供 jianpu_text 或 jianpu_file_id")

    file_service = FileService()
    import uuid
    out_name = f"{uuid.uuid4().hex[:12]}.musicxml"
    out_path = uploads.base_dir / out_name
    file_service.write_text(out_path, xml_text)

    musicxml_id = uploads.register(out_path)
    return JianpuToMusicXmlResponse(musicxml_text=xml_text, musicxml_file_id=musicxml_id)
