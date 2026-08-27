import { apiFetch, type ApiResult } from './client'
import type {
  MusicXmlToJianpuRequest,
  MusicXmlToJianpuResponse,
} from '../models/types'

export interface JianpuRekeyRequest {
  text: string
  previous_text: string
}

export interface JianpuRekeyResponse {
  transposed_text: string
}

export const convertApi = {
  musicxmlToJianpu(req: MusicXmlToJianpuRequest): Promise<ApiResult<MusicXmlToJianpuResponse>> {
    return apiFetch('/convert/musicxml-to-jianpu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  rekeyText(req: JianpuRekeyRequest): Promise<ApiResult<JianpuRekeyResponse>> {
    return apiFetch('/jianpu/rekey', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
