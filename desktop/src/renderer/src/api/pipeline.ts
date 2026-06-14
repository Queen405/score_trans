import { apiFetch } from './client'
import type { AccidentalMode, PipelineByFileIdRequest, TaskSubmitResponse } from '../models/types'

export const pipelineApi = {
  run(
    file: File,
    targetKey = 'C',
    accidentalMode: AccidentalMode = 'auto',
    startMeasureNumber?: number,
    title?: string,
  ): Promise<TaskSubmitResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    formData.append('accidental_mode', accidentalMode)
    if (startMeasureNumber !== undefined) {
      formData.append('start_measure_number', String(startMeasureNumber))
    }
    if (title) {
      formData.append('title', title)
    }
    return apiFetch('/pipeline', { method: 'POST', body: formData })
  },

  runByFileId(req: PipelineByFileIdRequest): Promise<TaskSubmitResponse> {
    return apiFetch('/pipeline/by-file-id', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
