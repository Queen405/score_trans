from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from ..dependencies import get_config
from ..schemas import SettingsResponse, SettingsUpdateRequest
from ...services.settings import ToolConfig

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    config: ToolConfig = Depends(get_config),
):
    """Get current tool configuration."""
    return SettingsResponse(
        audiveris_path=config.audiveris_path,
        musescore_path=config.musescore_path,
        java_home=config.java_home,
        work_dir=str(config.work_dir),
        output_dir=os.environ.get("SCORE_TRANS_OUTPUT_DIR", ""),
        ocr_api_key_set=bool(os.environ.get("SCORE_TRANS_OCR_API_KEY")),
        ocr_base_url=os.environ.get("SCORE_TRANS_OCR_BASE_URL", "https://api.siliconflow.cn/v1"),
        ocr_model=os.environ.get("SCORE_TRANS_OCR_MODEL", "deepseek-ai/DeepSeek-OCR"),
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    config: ToolConfig = Depends(get_config),
):
    """Update tool configuration. Changes are persisted to environment variables."""
    if req.audiveris_path is not None:
        os.environ["SCORE_TRANS_AUDIVERIS"] = req.audiveris_path
        config.audiveris_path = req.audiveris_path

    if req.musescore_path is not None:
        os.environ["SCORE_TRANS_MUSESCORE"] = req.musescore_path
        config.musescore_path = req.musescore_path

    if req.java_home is not None:
        os.environ["SCORE_TRANS_JAVA_HOME"] = req.java_home
        config.java_home = req.java_home

    if req.output_dir is not None:
        os.environ["SCORE_TRANS_OUTPUT_DIR"] = req.output_dir

    if req.ocr_api_key is not None:
        os.environ["SCORE_TRANS_OCR_API_KEY"] = req.ocr_api_key

    if req.ocr_base_url is not None:
        os.environ["SCORE_TRANS_OCR_BASE_URL"] = req.ocr_base_url

    if req.ocr_model is not None:
        os.environ["SCORE_TRANS_OCR_MODEL"] = req.ocr_model

    return SettingsResponse(
        audiveris_path=config.audiveris_path,
        musescore_path=config.musescore_path,
        java_home=config.java_home,
        work_dir=str(config.work_dir),
        output_dir=os.environ.get("SCORE_TRANS_OUTPUT_DIR", ""),
        ocr_api_key_set=bool(os.environ.get("SCORE_TRANS_OCR_API_KEY")),
        ocr_base_url=os.environ.get("SCORE_TRANS_OCR_BASE_URL", "https://api.siliconflow.cn/v1"),
        ocr_model=os.environ.get("SCORE_TRANS_OCR_MODEL", "deepseek-ai/DeepSeek-OCR"),
    )
