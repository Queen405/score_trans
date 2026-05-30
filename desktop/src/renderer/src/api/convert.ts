import { apiFetch } from './client'
import type {
  MusicXmlToJianpuRequest,
  MusicXmlToJianpuResponse,
  JianpuToMusicXmlRequest,
  JianpuToMusicXmlResponse,
} from '../models/types'

export const convertApi = {
  musicxmlToJianpu(req: MusicXmlToJianpuRequest): Promise<MusicXmlToJianpuResponse> {
    return apiFetch('/convert/musicxml-to-jianpu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  jianpuToMusicxml(req: JianpuToMusicXmlRequest): Promise<JianpuToMusicXmlResponse> {
    return apiFetch('/convert/jianpu-to-musicxml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
