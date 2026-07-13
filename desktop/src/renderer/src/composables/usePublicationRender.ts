import { onScopeDispose } from 'vue'
import { renderApi } from '../api/render'
import type {
  BatchRenderRequest,
  FinalOutputRequest,
  RenderJianpuSvgRequest,
  RenderJianpuTextSvgRequest,
} from '../models/types'

export function usePublicationRender() {
  let generation = 0
  let controller: AbortController | null = null

  function nextSignal(): { signal: AbortSignal; generation: number } {
    controller?.abort()
    controller = new AbortController()
    generation += 1
    return { signal: controller.signal, generation }
  }

  async function current<T>(request: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const state = nextSignal()
    const result = await request(state.signal)
    if (state.generation !== generation) throw new DOMException('渲染请求已过期', 'AbortError')
    return result
  }

  onScopeDispose(() => controller?.abort())

  return {
    jianpuSvg: (req: RenderJianpuSvgRequest) => current((signal) => renderApi.jianpuSvg(req, signal)),
    jianpuTextSvg: (req: RenderJianpuTextSvgRequest) => current((signal) => renderApi.jianpuTextSvg(req, signal)),
    finalOutput: (req: FinalOutputRequest) => current((signal) => renderApi.finalOutput(req, signal)),
    batchA4: (req: BatchRenderRequest) => current((signal) => renderApi.batchA4(req, signal)),
    normalizeJianpuText: renderApi.normalizeJianpuText,
    cancel: () => controller?.abort(),
  }
}
