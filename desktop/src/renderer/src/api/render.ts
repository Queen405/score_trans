import { apiFetch, type ApiResult } from './client'
export interface LiveJianpuSvgRequest { jianpu_text: string; title?: string; show_measure_numbers?: boolean; measure_number_mode?: string; initial_measure_number?: number }
export interface LiveJianpuSvgResponse { svg: string; jianpu_text: string }

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
  jianpuSvg(req: RenderJianpuSvgRequest, signal?: AbortSignal): Promise<ApiResult<RenderJianpuSvgResponse>> {
    return apiFetch('/render/jianpu-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  },

  jianpuTextSvg(req: RenderJianpuTextSvgRequest, signal?: AbortSignal): Promise<ApiResult<RenderJianpuTextSvgResponse>> {
    return apiFetch('/render/jianpu-text-svg', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  },

  finalOutput(req: FinalOutputRequest, signal?: AbortSignal): Promise<ApiResult<FinalOutputResponse>> {
    return apiFetch('/render/final-output', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  },

  batchA4(req: BatchRenderRequest, signal?: AbortSignal): Promise<ApiResult<BatchRenderResponse>> {
    return apiFetch('/render/batch-a4', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal,
    })
  },

  liveJianpuSvg(req: LiveJianpuSvgRequest, signal?: AbortSignal): Promise<ApiResult<LiveJianpuSvgResponse>> {
    return apiFetch("/render/jianpu-live-svg", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req), signal })
  },

  normalizeJianpuText(req: NormalizeJianpuTextRequest): Promise<ApiResult<NormalizeJianpuTextResponse>> {
    return apiFetch('/render/normalize-jianpu-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
  },
}
