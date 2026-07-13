import { apiFetch, type ApiResult } from './client'
import type { Schemas } from '../models/openapi'

const BASE = '/api/correct'

export const correctApi = {
  getEntities(
    omrFileId: string,
    sourceMapFileId?: string,
  ): Promise<ApiResult<Schemas['EntitiesResponse']>> {
    const params = new URLSearchParams({ omr_file_id: omrFileId })
    if (sourceMapFileId) params.set('source_map_file_id', sourceMapFileId)
    return apiFetch(`${BASE}/entities?${params}`)
  },

  apply(req: Schemas['CorrectionRequest']): Promise<ApiResult<Schemas['CorrectionResponse']>> {
    return apiFetch(`${BASE}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
