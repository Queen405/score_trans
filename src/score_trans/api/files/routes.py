from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse

from ..dependencies import get_file_actions
from ...exec.files.actions import FileActions
from ...models.files.schemas import UploadResponse

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = ...,
    actions: FileActions = Depends(get_file_actions),
):
    return actions.upload_file(file)


@router.get("/{file_id}")
async def download_file(
    file_id: str,
    actions: FileActions = Depends(get_file_actions),
):
    path, media_type = actions.download_file(file_id)
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    actions: FileActions = Depends(get_file_actions),
):
    return actions.delete_file(file_id)

