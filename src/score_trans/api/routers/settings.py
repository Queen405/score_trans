from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_config
from ..schemas import SettingsResponse, SettingsUpdateRequest
from ...services.settings import ToolConfig
from ...services.settings_db import SettingsDB

router = APIRouter(prefix="/settings", tags=["settings"])

_db = SettingsDB.default()


def _resp() -> SettingsResponse:
    all_settings = _db.get_all()
    return SettingsResponse(
        audiveris_path=all_settings.get("audiveris_path", ""),
        musescore_path=all_settings.get("musescore_path", ""),
        java_home=all_settings.get("java_home", ""),
        work_dir=str(get_config().work_dir),
        output_dir=all_settings.get("output_dir", ""),
        ocr_api_key=all_settings.get("ocr_api_key", ""),
        ocr_api_key_set=bool(all_settings.get("ocr_api_key", "")),
        ocr_base_url=all_settings.get("ocr_base_url", "https://api.siliconflow.cn/v1"),
        ocr_model=all_settings.get("ocr_model", "deepseek-ai/DeepSeek-OCR"),
        omr_preprocess=_db.get_bool("omr_preprocess", True),
        omr_preprocess_long_edge=_db.get_int("omr_preprocess_long_edge", 3600),
        omr_preprocess_binarize=_db.get_bool("omr_preprocess_binarize", False),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """Get current tool configuration."""
    return _resp()


@router.put("", response_model=SettingsResponse)
async def update_settings(
    req: SettingsUpdateRequest,
    config: ToolConfig = Depends(get_config),
):
    """Update tool configuration."""
    if req.audiveris_path is not None:
        _db.set("audiveris_path", req.audiveris_path)
        config.audiveris_path = req.audiveris_path

    if req.musescore_path is not None:
        _db.set("musescore_path", req.musescore_path)
        config.musescore_path = req.musescore_path

    if req.java_home is not None:
        _db.set("java_home", req.java_home)
        config.java_home = req.java_home

    if req.output_dir is not None:
        _db.set("output_dir", req.output_dir)

    if req.ocr_api_key is not None:
        _db.set("ocr_api_key", req.ocr_api_key)

    if req.ocr_base_url is not None:
        _db.set("ocr_base_url", req.ocr_base_url)

    if req.ocr_model is not None:
        _db.set("ocr_model", req.ocr_model)

    if req.omr_preprocess is not None:
        _db.set("omr_preprocess", "1" if req.omr_preprocess else "0")
        config.omr_preprocess = req.omr_preprocess

    if req.omr_preprocess_long_edge is not None:
        value = max(0, req.omr_preprocess_long_edge)
        _db.set("omr_preprocess_long_edge", str(value))
        config.omr_preprocess_long_edge = value

    if req.omr_preprocess_binarize is not None:
        _db.set("omr_preprocess_binarize", "1" if req.omr_preprocess_binarize else "0")
        config.omr_preprocess_binarize = req.omr_preprocess_binarize

    return _resp()
