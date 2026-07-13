from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, UploadFile

from ..dependencies import get_export_actions
from ...exec.export.actions import ExportActions
from ...models.export.schemas import (
    ExportMidiRequest,
    ExportMidiTextRequest,
    ExportFilesResponse,
    ExportMusicXmlRequest,
    ExportMusicXmlTextRequest,
    ExportRenderedImagesRequest,
    ExportRenderedPdfRequest,
    ExportResponse,
)

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/midi", response_model=ExportResponse)
async def export_midi(
    req: ExportMidiRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_midi, req)


@router.post("/midi-text", response_model=ExportResponse)
async def export_midi_text(
    req: ExportMidiTextRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_midi_text, req)


@router.post("/pdf", response_model=ExportResponse)
async def export_pdf(
    files: list[UploadFile] = File(..., description="PNG 或 JPEG images, one per page"),
    filename: str = "jianpu.pdf",
    actions: ExportActions = Depends(get_export_actions),
):
    return await actions.export_pdf(files, filename=filename)


@router.post("/rendered-pdf", response_model=ExportResponse)
async def export_rendered_pdf(
    req: ExportRenderedPdfRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_rendered_pdf, req)


@router.post("/rendered-images", response_model=ExportFilesResponse)
async def export_rendered_images(
    req: ExportRenderedImagesRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_rendered_images, req)


@router.post("/musicxml", response_model=ExportResponse)
async def export_musicxml(
    req: ExportMusicXmlRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_musicxml, req)


@router.post("/musicxml-text", response_model=ExportResponse)
async def export_musicxml_text(
    req: ExportMusicXmlTextRequest,
    actions: ExportActions = Depends(get_export_actions),
):
    return await asyncio.to_thread(actions.export_musicxml_text, req)
