import { apiFetch, type ApiResult } from './client'
import type {
  BatchRenderRequest,
  BatchRenderResponse,
  RenderJianpuSvgRequest,
  RenderJianpuSvgResponse,
  RenderJianpuTextSvgRequest,
  RenderJianpuTextSvgResponse,
  NormalizeJianpuTextRequest,
  NormalizeJianpuTextResponse,
  FinalOutputRequest,
  FinalOutputResponse,
} from '../models/types'

export const renderApi = {
  jianpuSvg(req: RenderJianpuSvgRequest): Promise<ApiResult<RenderJianpuSvgResponse>> {
    return apiFetch('/render/jianpu-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  jianpuTextSvg(req: RenderJianpuTextSvgRequest): Promise<ApiResult<RenderJianpuTextSvgResponse>> {
    return apiFetch('/render/jianpu-text-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  finalOutput(req: FinalOutputRequest): Promise<ApiResult<FinalOutputResponse>> {
    return apiFetch('/render/final-output', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  batchA4(req: BatchRenderRequest): Promise<ApiResult<BatchRenderResponse>> {
    return apiFetch('/render/batch-a4', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },

  normalizeJianpuText(req: NormalizeJianpuTextRequest): Promise<ApiResult<NormalizeJianpuTextResponse>> {
    return apiFetch('/render/normalize-jianpu-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
