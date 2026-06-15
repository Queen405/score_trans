from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_history_actions
from ...exec.history.actions import HistoryActions
from ...models.history.schemas import (
    BatchCreateRequest,
    BatchListItem,
    BatchRenderPagesUpdate,
    BatchResponse,
    DeleteAllResponse,
    PageResponse,
    PageUpdate,
)

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[BatchListItem])
def list_history(actions: HistoryActions = Depends(get_history_actions)):
    return actions.list_history()


@router.post("", response_model=BatchResponse, status_code=201)
def create_batch(
    req: BatchCreateRequest,
    actions: HistoryActions = Depends(get_history_actions),
):
    return actions.create_batch(req)


@router.get("/{batch_id}", response_model=BatchResponse)
def get_history(
    batch_id: int,
    actions: HistoryActions = Depends(get_history_actions),
):
    return actions.get_history(batch_id)


@router.patch("/pages/{page_id}", response_model=PageResponse)
def update_history_page(
    page_id: int,
    req: PageUpdate,
    actions: HistoryActions = Depends(get_history_actions),
):
    return actions.update_history_page(page_id, req)


@router.patch("/{batch_id}/render-pages", response_model=BatchResponse)
def update_batch_render_pages(
    batch_id: int,
    req: BatchRenderPagesUpdate,
    actions: HistoryActions = Depends(get_history_actions),
):
    return actions.update_batch_render_pages(batch_id, req)


@router.delete("/{batch_id}")
def delete_history(
    batch_id: int,
    actions: HistoryActions = Depends(get_history_actions),
):
    return actions.delete_history(batch_id)


@router.delete("", response_model=DeleteAllResponse)
def delete_all_history(actions: HistoryActions = Depends(get_history_actions)):
    return actions.delete_all_history()
