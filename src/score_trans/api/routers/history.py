from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...services.history_service import HistoryEntry, HistoryService

router = APIRouter(prefix="/history", tags=["history"])
_service = HistoryService()


class HistoryCreateRequest(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    svg_file_id: str = ""
    status: str = "completed"
    error_message: str = ""


class HistoryResponse(BaseModel):
    id: int
    created_at: str
    input_file_name: str
    input_file_id: str
    musicxml_file_id: str
    jianpu_text: str
    svg_file_id: str
    status: str
    error_message: str


class HistoryDeleteAllResponse(BaseModel):
    deleted_count: int


def _entry_to_response(entry: HistoryEntry) -> HistoryResponse:
    return HistoryResponse(
        id=entry.id,
        created_at=entry.created_at,
        input_file_name=entry.input_file_name,
        input_file_id=entry.input_file_id,
        musicxml_file_id=entry.musicxml_file_id,
        jianpu_text=entry.jianpu_text,
        svg_file_id=entry.svg_file_id,
        status=entry.status,
        error_message=entry.error_message,
    )


@router.get("", response_model=list[HistoryResponse])
def list_history():
    """List all history entries, most recent first."""
    return [_entry_to_response(e) for e in _service.list_entries()]


@router.post("", response_model=HistoryResponse, status_code=201)
def create_history(req: HistoryCreateRequest):
    """Create a new history entry."""
    entry = HistoryEntry(
        input_file_name=req.input_file_name,
        input_file_id=req.input_file_id,
        musicxml_file_id=req.musicxml_file_id,
        jianpu_text=req.jianpu_text,
        svg_file_id=req.svg_file_id,
        status=req.status,
        error_message=req.error_message,
    )
    return _entry_to_response(_service.create_entry(entry))


@router.get("/{entry_id}", response_model=HistoryResponse)
def get_history(entry_id: int):
    """Get a single history entry by ID."""
    entry = _service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")
    return _entry_to_response(entry)


@router.delete("/{entry_id}")
def delete_history(entry_id: int):
    """Delete a single history entry."""
    if not _service.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"ok": True}


@router.delete("", response_model=HistoryDeleteAllResponse)
def delete_all_history():
    """Delete all history entries."""
    count = _service.delete_all()
    return HistoryDeleteAllResponse(deleted_count=count)
