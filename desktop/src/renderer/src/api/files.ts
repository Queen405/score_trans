import { apiFetch } from './client'

export const filesApi = {
  async existsMany(fileIds: string[]): Promise<Record<string, boolean>> {
    const uniqueIds = [...new Set(fileIds.filter(Boolean))]
    if (!uniqueIds.length) return {}
    const response = await apiFetch<{ files: Record<string, boolean> }>('/files/exists', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_ids: uniqueIds }),
    })
    return response.files
  },
}
