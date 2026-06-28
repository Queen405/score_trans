import { apiFetch, type ApiResult } from './client'
import type { CacheCleanupResponse, SettingsResponse, SettingsUpdateRequest } from '../models/types'

export interface SettingsQuery {
  ocr_provider?: string
  ai_provider?: string
  assistant_provider?: string
}

export const settingsApi = {
  get(query: SettingsQuery = {}): Promise<ApiResult<SettingsResponse>> {
    const params = new URLSearchParams()
    if (query.ocr_provider) params.set('ocr_provider', query.ocr_provider)
    if (query.ai_provider) params.set('ai_provider', query.ai_provider)
    if (query.assistant_provider) params.set('assistant_provider', query.assistant_provider)
    const suffix = params.toString()
    return apiFetch(`/settings${suffix ? `?${suffix}` : ''}`)
  },

  update(req: SettingsUpdateRequest): Promise<ApiResult<SettingsResponse>> {
    return apiFetch('/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  clearCache(): Promise<ApiResult<CacheCleanupResponse>> {
    return apiFetch('/settings/cache', {
      method: 'DELETE',
    })
  },
}
