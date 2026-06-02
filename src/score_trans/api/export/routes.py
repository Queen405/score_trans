from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..dependencies import get_export_actions
from ...exec.export.actions import ExportActions
from ...models.export.schemas import ExportMidiTextRequest, ExportResponse

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/midi", response_model=ExportResponse)
async def export_midi(
    musicxml_file_id: str,
    filename: str | None = None,
    actions: ExportActions = Depends(get_export_actions),
):
    return actions.export_midi(musicxml_file_id, filename=filename)


@router.post("/midi-text", response_model=ExportResponse)
async def export_midi_text(
    req: ExportMidiTextRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return actions.export_midi_text(req)


@router.post("/pdf", response_model=ExportResponse)
async def export_pdf(
    files: list[UploadFile] = File(..., description="PNG images, one per page"),
    filename: str = "jianpu.pdf",
    actions: ExportActions = Depends(get_export_actions),
):
    return await actions.export_pdf(files, filename=filename)

