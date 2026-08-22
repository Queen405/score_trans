import { onScopeDispose } from 'vue'
import { renderApi } from '../api/render'
import { RenderRequestGate } from '../utils/renderRequestGate'
import type {
  BatchRenderRequest,
  FinalOutputRequest,
  RenderJianpuSvgRequest,
  RenderJianpuTextSvgRequest,
} from '../models/types'

export function usePublicationRender() {
  const gate = new RenderRequestGate()

  onScopeDispose(() => gate.dispose())

  return {
    jianpuSvg: (req: RenderJianpuSvgRequest) => gate.current((signal) => renderApi.jianpuSvg(req, signal)),
    jianpuTextSvg: (req: RenderJianpuTextSvgRequest) => gate.current((signal) => renderApi.jianpuTextSvg(req, signal)),
    finalOutput: (req: FinalOutputRequest) => gate.current((signal) => renderApi.finalOutput(req, signal)),
    batchA4: (req: BatchRenderRequest) => gate.current((signal) => renderApi.batchA4(req, signal)),
    normalizeJianpuText: renderApi.normalizeJianpuText,
    cancel: () => gate.cancel(),
  }
}
