from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse, Response

from ..dependencies import get_file_actions
from ...exec.files.actions import FileActions
from ...models.files.schemas import (
    FilesExistRequest,
    FilesExistResponse,
    RotateFileRequest,
    UploadResponse,
)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = ...,
    actions: FileActions = Depends(get_file_actions),
):
    return await asyncio.to_thread(actions.upload_file, file)


@router.post("/exists", response_model=FilesExistResponse)
async def files_exist(
    req: FilesExistRequest,
    actions: FileActions = Depends(get_file_actions),
):
    return await asyncio.to_thread(actions.files_exist, req.file_ids)


@router.post("/{file_id}/rotate", response_model=UploadResponse)
async def rotate_file(
    file_id: str,
    req: RotateFileRequest,
    actions: FileActions = Depends(get_file_actions),
):
    return await asyncio.to_thread(actions.rotate_file, file_id, req.direction)


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    actions: FileActions = Depends(get_file_actions),
):
    path, media_type = await asyncio.to_thread(actions.download_file, file_id)
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={"Cache-Control": "private, no-store"},
    )


@router.head("/{file_id}")
async def head_file(
    file_id: str,
    actions: FileActions = Depends(get_file_actions),
):
    path, media_type = await asyncio.to_thread(actions.download_file, file_id)
    return Response(
        status_code=200,
        headers={
            "Content-Type": media_type,
            "Content-Length": str(path.stat().st_size),
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    actions: FileActions = Depends(get_file_actions),
):
    return await asyncio.to_thread(actions.delete_file, file_id)
