import { apiFetch } from './client'
import type {
  RenderJianpuSvgRequest,
  RenderJianpuSvgResponse,
  RenderJianpuTextSvgRequest,
  RenderJianpuTextSvgResponse,
  FinalOutputRequest,
  FinalOutputResponse,
} from '../models/types'

export const renderApi = {
  jianpuSvg(req: RenderJianpuSvgRequest): Promise<RenderJianpuSvgResponse> {
    return apiFetch('/render/jianpu-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  jianpuTextSvg(req: RenderJianpuTextSvgRequest): Promise<RenderJianpuTextSvgResponse> {
    return apiFetch('/render/jianpu-text-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  finalOutput(req: FinalOutputRequest): Promise<FinalOutputResponse> {
    return apiFetch('/render/final-output', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
