from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..dependencies import get_config, get_pipeline, get_upload_manager
from ..schemas import PipelineResponse
from ..uploads import UploadManager
from ...use_cases import FullPipelineUseCase
from ...services.settings import ToolConfig
from ...services.file_service import FileService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("", response_model=PipelineResponse)
async def run_pipeline(
    file: UploadFile = File(...),
    target_key: str = Form("C"),
    start_measure_number: int | None = Form(None),
    title: str | None = Form(None),
    pipeline_uc: FullPipelineUseCase = Depends(get_pipeline),
    config: ToolConfig = Depends(get_config),
    uploads: UploadManager = Depends(get_upload_manager),
):
    """Full pipeline: upload → recognize → convert → render → return all outputs."""
    # Save the uploaded file
    file_id = uploads.save(file)
    input_path = uploads.get_path(file_id)
    if not input_path:
        raise HTTPException(500, "文件保存失败")

    # Create a temporary output directory for the pipeline
    import uuid
    output_dir = config.work_dir / "pipeline" / uuid.uuid4().hex[:12]
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run the full pipeline using existing use_case
    outputs = pipeline_uc.execute(
        input_path,
        output_dir,
        config=config,
        target_key=target_key,
        start_measure_number=start_measure_number,
        title=title,
    )

    # Register all output files
    musicxml_id = uploads.register(outputs.musicxml_path)
    jianpu_id = uploads.register(outputs.jianpu_text_path)
    svg_id = uploads.register(outputs.jianpu_svg_path)

    # Read jianpu text for inline response
    file_service = FileService()
    jianpu_text = file_service.read_text(outputs.jianpu_text_path)

    return PipelineResponse(
        musicxml_file_id=musicxml_id,
        jianpu_text=jianpu_text,
        jianpu_file_id=jianpu_id,
        svg_file_id=svg_id,
    )
