from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..dependencies import get_config, get_recognize, get_upload_manager
from ..schemas import RecognizeResponse
from ..uploads import UploadManager
from ...use_cases import RecognizeScoreUseCase
from ...services.settings import ToolConfig

router = APIRouter(prefix="/recognize", tags=["recognize"])


@router.post("", response_model=RecognizeResponse)
async def recognize(
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    recognize_uc: RecognizeScoreUseCase = Depends(get_recognize),
    config: ToolConfig = Depends(get_config),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Upload an image/PDF and recognize it as MusicXML via Audiveris OMR."""
    # Save the uploaded file
    file_id = uploads.save(file)
    input_path = uploads.get_path(file_id)
    if not input_path:
        raise HTTPException(500, "文件保存失败")

    # Run OMR recognition using existing use_case
    output_dir = config.work_dir / "audiveris"
    musicxml_path = recognize_uc.execute(input_path, output_dir, config)

    # Register the output MusicXML
    musicxml_id = uploads.register(musicxml_path)

    return RecognizeResponse(
        musicxml_file_id=musicxml_id,
        musicxml_filename=musicxml_path.name,
    )
