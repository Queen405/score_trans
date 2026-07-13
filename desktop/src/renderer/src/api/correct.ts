import { apiFetch, type ApiResult } from './client'
import type { CorrectionRequest, CorrectionResponse, EntitiesResponse } from '../models/types'

const BASE = '/correct'

export const correctApi = {
  getEntities(
    omrFileId: string,
    sourceMapFileId: string,
    signal?: AbortSignal,
  ): Promise<ApiResult<EntitiesResponse>> {
    const params = new URLSearchParams({
      omr_file_id: omrFileId,
      source_map_file_id: sourceMapFileId,
    })
    return apiFetch(`${BASE}/entities?${params}`, { signal })
  },

  apply(req: CorrectionRequest): Promise<ApiResult<CorrectionResponse>> {
    return apiFetch(`${BASE}/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
