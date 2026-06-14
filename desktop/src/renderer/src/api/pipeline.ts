import { apiFetch } from './client'
import type { AccidentalMode, MeasureNumberMode, PipelineByFileIdRequest, TargetKey, TaskSubmitResponse } from '../models/types'

export const pipelineApi = {
  run(
    file: File,
    targetKey: TargetKey = 'C',
    accidentalMode: AccidentalMode = 'auto',
    startMeasureNumber?: number,
    measureNumberMode: MeasureNumberMode = 'all',
    title?: string,
  ): Promise<TaskSubmitResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    formData.append('accidental_mode', accidentalMode)
    formData.append('measure_number_mode', measureNumberMode)
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
