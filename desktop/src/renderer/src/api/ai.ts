import { apiFetch } from './client'
import type { AiTranscribeRequest, AiTranscribeResponse } from '../models/types'

export const aiApi = {
  transcribe(req: AiTranscribeRequest): Promise<AiTranscribeResponse> {
    return apiFetch('/ai/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
