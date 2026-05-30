import { apiFetch } from './client'
import type { PipelineResponse } from '../models/types'

export const pipelineApi = {
  run(
    file: File,
    targetKey = 'C',
    startMeasureNumber?: number,
    title?: string,
  ): Promise<PipelineResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    if (startMeasureNumber !== undefined) {
      formData.append('start_measure_number', String(startMeasureNumber))
    }
    if (title) {
      formData.append('title', title)
    }
    return apiFetch('/pipeline', { method: 'POST', body: formData })
  },
}
