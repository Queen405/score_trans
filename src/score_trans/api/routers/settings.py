from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from ..dependencies import get_config
from ..schemas import SettingsResponse, SettingsUpdateRequest
from ...services.settings import ToolConfig
from ...services.settings_db import SettingsDB

router = APIRouter(prefix="/settings", tags=["settings"])

_db = SettingsDB()

DEFAULTS = {
    "ocr_base_url": "https://api.siliconflow.cn/v1",
    "ocr_model": "deepseek-ai/DeepSeek-OCR",
}


def _ocr(key: str) -> str:
    return _db.get(key, DEFAULTS.get(key, ""))


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
        ocr_api_key=_ocr("ocr_api_key"),
        ocr_api_key_set=bool(_ocr("ocr_api_key")),
        ocr_base_url=_ocr("ocr_base_url"),
        ocr_model=_ocr("ocr_model"),
        omr_preprocess=config.omr_preprocess,
        omr_preprocess_long_edge=config.omr_preprocess_long_edge,
        omr_preprocess_binarize=config.omr_preprocess_binarize,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    config: ToolConfig = Depends(get_config),
):
    """Update tool configuration."""
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

    # Persist OCR settings to SQLite
    if req.ocr_api_key is not None:
        _db.set("ocr_api_key", req.ocr_api_key)
        os.environ["SCORE_TRANS_OCR_API_KEY"] = req.ocr_api_key

    if req.ocr_base_url is not None:
        _db.set("ocr_base_url", req.ocr_base_url)
        os.environ["SCORE_TRANS_OCR_BASE_URL"] = req.ocr_base_url

    if req.ocr_model is not None:
        _db.set("ocr_model", req.ocr_model)
        os.environ["SCORE_TRANS_OCR_MODEL"] = req.ocr_model

    if req.omr_preprocess is not None:
        os.environ["SCORE_TRANS_OMR_PREPROCESS"] = "1" if req.omr_preprocess else "0"
        config.omr_preprocess = req.omr_preprocess

    if req.omr_preprocess_long_edge is not None:
        value = max(0, req.omr_preprocess_long_edge)
        os.environ["SCORE_TRANS_OMR_PREPROCESS_LONG_EDGE"] = str(value)
        config.omr_preprocess_long_edge = value

    if req.omr_preprocess_binarize is not None:
        os.environ["SCORE_TRANS_OMR_PREPROCESS_BINARIZE"] = "1" if req.omr_preprocess_binarize else "0"
        config.omr_preprocess_binarize = req.omr_preprocess_binarize

    return SettingsResponse(
        audiveris_path=config.audiveris_path,
        musescore_path=config.musescore_path,
        java_home=config.java_home,
        work_dir=str(config.work_dir),
        output_dir=os.environ.get("SCORE_TRANS_OUTPUT_DIR", ""),
        ocr_api_key_set=bool(_ocr("ocr_api_key")),
        ocr_base_url=_ocr("ocr_base_url"),
        ocr_model=_ocr("ocr_model"),
        omr_preprocess=config.omr_preprocess,
        omr_preprocess_long_edge=config.omr_preprocess_long_edge,
        omr_preprocess_binarize=config.omr_preprocess_binarize,
    )
