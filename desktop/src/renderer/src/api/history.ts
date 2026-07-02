import { apiFetch, type ApiResult } from './client'
import type {
  HistoryBatch,
  HistoryBatchJianpuTextUpdateRequest,
  HistoryBatchListItem,
  HistoryBatchPageOrderRequest,
  HistoryBatchRenderPageOcrTextsUpdateRequest,
  HistoryBatchRenderPagesUpdateRequest,
  HistoryCreateRequest,
  HistoryPage,
  HistoryPageUpdateRequest,
} from '../models/types'
import { createKeyedAsyncQueue } from '../utils/asyncCoordination'

const pageUpdateQueue = createKeyedAsyncQueue<number>()

export const historyApi = {
  list(): Promise<ApiResult<HistoryBatchListItem[]>> {
    return apiFetch('/history')
  },

  get(id: number): Promise<ApiResult<HistoryBatch>> {
    return apiFetch(`/history/${id}`)
  },

  getPage(id: number): Promise<ApiResult<HistoryPage>> {
    return apiFetch(`/history/pages/${id}`)
  },

  create(req: HistoryCreateRequest): Promise<ApiResult<HistoryBatch>> {
    return apiFetch('/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  updatePage(id: number, req: HistoryPageUpdateRequest): Promise<ApiResult<HistoryPage>> {
    return pageUpdateQueue.enqueue(id, () =>
      apiFetch(`/history/pages/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }),
    )
  },

  updateBatchRenderPages(id: number, req: HistoryBatchRenderPagesUpdateRequest): Promise<ApiResult<HistoryBatch>> {
    return apiFetch(`/history/${id}/render-pages`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  updateBatchJianpuText(id: number, req: HistoryBatchJianpuTextUpdateRequest): Promise<ApiResult<HistoryBatch>> {
    return apiFetch(`/history/${id}/jianpu-text`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  updateBatchRenderPageOcrTexts(id: number, req: HistoryBatchRenderPageOcrTextsUpdateRequest): Promise<ApiResult<HistoryBatch>> {
    return apiFetch(`/history/${id}/render-page-ocr-texts`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  reorderPages(id: number, req: HistoryBatchPageOrderRequest): Promise<ApiResult<HistoryBatch>> {
    return apiFetch(`/history/${id}/page-order`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  deleteOne(id: number): Promise<ApiResult<{ ok: boolean }>> {
    return apiFetch(`/history/${id}`, { method: 'DELETE' })
  },

  deleteAll(): Promise<ApiResult<{ deleted_count: number }>> {
    return apiFetch('/history', { method: 'DELETE' })
  },
}
