import { apiFetch } from './client'
import type { HistoryEntry, HistoryCreateRequest } from '../models/types'

export const historyApi = {
  list(): Promise<HistoryEntry[]> {
    return apiFetch('/history')
  },

  create(req: HistoryCreateRequest): Promise<HistoryEntry> {
    return apiFetch('/history', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  get(id: number): Promise<HistoryEntry> {
    return apiFetch(`/history/${id}`)
  },

  deleteOne(id: number): Promise<{ ok: boolean }> {
    return apiFetch(`/history/${id}`, { method: 'DELETE' })
  },

  deleteAll(): Promise<{ deleted_count: number }> {
    return apiFetch('/history', { method: 'DELETE' })
  },
}
