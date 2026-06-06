import { apiFetch } from './client'
import type { TaskSubmitResponse } from '../models/types'

export const recognizeApi = {
  recognize(
    file: File,
    targetKey = 'C',
    startMeasureNumber?: number,
  ): Promise<TaskSubmitResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    if (startMeasureNumber !== undefined) {
      formData.append('start_measure_number', String(startMeasureNumber))
    }
    return apiFetch('/recognize', { method: 'POST', body: formData })
  },
}
