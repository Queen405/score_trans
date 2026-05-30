import { apiFetch } from './client'
import type { SettingsResponse, SettingsUpdateRequest } from '../models/types'

export const settingsApi = {
  get(): Promise<SettingsResponse> {
    return apiFetch('/settings')
  },

  update(req: SettingsUpdateRequest): Promise<SettingsResponse> {
    return apiFetch('/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
