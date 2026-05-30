import { apiFetch, getFileURL } from './client'
import type { ExportRequest, ExportResponse } from '../models/types'

export const exportApi = {
  exportScore(req: ExportRequest): Promise<ExportResponse> {
    return apiFetch('/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  getDownloadURL(fileId: string): string {
    return getFileURL(fileId)
  },
}
