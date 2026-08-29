import { apiFetch, type ApiResult } from './client'
import type { JianpuRekeyRequest, JianpuRekeyResponse } from '../models/types'

export const jianpuApi = {
  rekeyText(req: JianpuRekeyRequest): Promise<ApiResult<JianpuRekeyResponse>> {
    return apiFetch('/jianpu/rekey', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
