import { apiFetch, type ApiResult } from './client'
import type {
  AccidentalMode,
  InstrumentProfile,
  MeasureNumberMode,
  PipelineByFileIdRequest,
  TargetKey,
  TaskSubmitResponse,
} from '../models/types'

export const pipelineApi = {
  run(
    file: File,
    targetKey: TargetKey = 'C',
    accidentalMode: AccidentalMode = 'auto',
    instrumentProfile: InstrumentProfile = 'general',
    measureNumberMode: MeasureNumberMode = 'all',
    title?: string,
    contentScalePercent = 67,
    systemGapPercent = 92,
    shortNoteGapPercent = 90,
    beatGapPercent = 100,
  ): Promise<ApiResult<TaskSubmitResponse>> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_key', targetKey)
    formData.append('accidental_mode', accidentalMode)
    formData.append('instrument_profile', instrumentProfile)
    formData.append('measure_number_mode', measureNumberMode)
    formData.append('jianpu_content_scale_percent', String(contentScalePercent))
    formData.append('jianpu_system_gap_percent', String(systemGapPercent))
    formData.append('jianpu_short_note_gap_percent', String(shortNoteGapPercent))
    formData.append('jianpu_beat_gap_percent', String(beatGapPercent))
    if (title) {
      formData.append('title', title)
    }
    return apiFetch('/pipeline', { method: 'POST', body: formData })
  },

  runByFileId(req: PipelineByFileIdRequest): Promise<ApiResult<TaskSubmitResponse>> {
    return apiFetch('/pipeline/by-file-id', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
