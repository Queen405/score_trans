import { apiFetch } from './client'
import type {
  HistoryBatch,
  HistoryBatchListItem,
  HistoryBatchRenderPagesUpdateRequest,
  HistoryCreateRequest,
  HistoryPage,
  HistoryPageUpdateRequest,
} from '../models/types'

export const historyApi = {
  list(): Promise<HistoryBatchListItem[]> {
    return apiFetch('/history')
  },

  get(id: number): Promise<HistoryBatch> {
    return apiFetch(`/history/${id}`)
  },

  create(req: HistoryCreateRequest): Promise<HistoryBatch> {
    return apiFetch('/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  updatePage(id: number, req: HistoryPageUpdateRequest): Promise<HistoryPage> {
    return apiFetch(`/history/pages/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  updateBatchRenderPages(id: number, req: HistoryBatchRenderPagesUpdateRequest): Promise<HistoryBatch> {
    return apiFetch(`/history/${id}/render-pages`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  deleteOne(id: number): Promise<{ ok: boolean }> {
    return apiFetch(`/history/${id}`, { method: 'DELETE' })
  },

  deleteAll(): Promise<{ deleted_count: number }> {
    return apiFetch('/history', { method: 'DELETE' })
  },
}
