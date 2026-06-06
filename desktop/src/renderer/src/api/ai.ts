import { apiFetch } from './client'
import type { AiTranscribeRequest, TaskSubmitResponse } from '../models/types'

export const aiApi = {
  transcribe(req: AiTranscribeRequest): Promise<TaskSubmitResponse> {
    return apiFetch('/ai/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
