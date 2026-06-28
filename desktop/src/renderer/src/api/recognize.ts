import { apiFetch, type ApiResult } from './client'
import type { TaskSubmitResponse } from '../models/types'

export const recognizeApi = {
  recognize(file: File): Promise<ApiResult<TaskSubmitResponse>> {
    const formData = new FormData()
    formData.append('file', file)
    return apiFetch('/recognize', { method: 'POST', body: formData })
  },
}
