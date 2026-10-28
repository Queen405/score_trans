import {
  apiFailure,
  apiFetch,
  apiSuccess,
  type ApiResult,
} from './client'
import type { UploadResponse } from '../models/types'

export type ImageRotationDirection = 'left' | 'right'

export const filesApi = {
  async existsMany(fileIds: string[]): Promise<ApiResult<Record<string, boolean>>> {
    const uniqueIds = [...new Set(fileIds.filter(Boolean))]
    if (!uniqueIds.length) return apiSuccess({})
    const response = await apiFetch<{ files: Record<string, boolean> }>('/files/exists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids: uniqueIds }),
    })
    if (response.error) return apiFailure(response.error)
    return apiSuccess(response.data.files)
  },

  rotate(fileId: string, direction: ImageRotationDirection): Promise<ApiResult<UploadResponse>> {
    return apiFetch(`/files/${encodeURIComponent(fileId)}/rotate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction }),
    })
  },
}
