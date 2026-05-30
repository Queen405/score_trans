from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...services.history_service import HistoryPage, HistoryService

router = APIRouter(prefix="/history", tags=["history"])
_service = HistoryService()


class PageCreate(BaseModel):
    input_file_name: str = ""
    input_file_id: str = ""
    musicxml_file_id: str = ""
    jianpu_text: str = ""
    svg_file_id: str = ""
    status: str = "completed"
    error_message: str = ""


class PageResponse(BaseModel):
    id: int
    input_file_name: str
    input_file_id: str
    musicxml_file_id: str
    jianpu_text: str
    svg_file_id: str
    status: str
    error_message: str


class BatchCreateRequest(BaseModel):
    pages: list[PageCreate]


class BatchResponse(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    pages: list[PageResponse]


class BatchListItem(BaseModel):
    id: int
    created_at: str
    page_count: int
    status: str
    first_file_name: str


class DeleteAllResponse(BaseModel):
    deleted_count: int


def _page_to_response(p: HistoryPage) -> PageResponse:
    return PageResponse(
        id=p.id,
        input_file_name=p.input_file_name,
        input_file_id=p.input_file_id,
        musicxml_file_id=p.musicxml_file_id,
        jianpu_text=p.jianpu_text,
        svg_file_id=p.svg_file_id,
        status=p.status,
        error_message=p.error_message,
    )


def _batch_to_response(batch) -> BatchResponse:
    return BatchResponse(
        id=batch.id,
        created_at=batch.created_at,
        page_count=batch.page_count,
        status=batch.status,
        pages=[_page_to_response(p) for p in batch.pages],
    )


@router.get("", response_model=list[BatchListItem])
def list_history():
    batches = _service.list_batches()
    result = []
    for b in batches:
        first_name = b.pages[0].input_file_name if b.pages else ""
        result.append(
            BatchListItem(
                id=b.id,
                created_at=b.created_at,
                page_count=b.page_count,
                status=b.status,
                first_file_name=first_name,
            )
        )
    return result


@router.post("", response_model=BatchResponse, status_code=201)
def create_batch(req: BatchCreateRequest):
    pages = [
        HistoryPage(
            input_file_name=p.input_file_name,
            input_file_id=p.input_file_id,
            musicxml_file_id=p.musicxml_file_id,
            jianpu_text=p.jianpu_text,
            svg_file_id=p.svg_file_id,
            status=p.status,
            error_message=p.error_message,
        )
        for p in req.pages
    ]
    batch = _service.create_batch(pages)
    return _batch_to_response(batch)


@router.get("/{batch_id}", response_model=BatchResponse)
def get_history(batch_id: int):
    batch = _service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return _batch_to_response(batch)


@router.delete("/{batch_id}")
def delete_history(batch_id: int):
    if not _service.delete_batch(batch_id):
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"ok": True}


@router.delete("", response_model=DeleteAllResponse)
def delete_all_history():
    count = _service.delete_all()
    return DeleteAllResponse(deleted_count=count)
