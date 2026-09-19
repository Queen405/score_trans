import { onScopeDispose } from 'vue'
import { renderApi } from '../api/render'
import { t } from '../i18n'
import { RenderRequestGate } from '../utils/renderRequestGate'
import type {
  BatchRenderRequest,
  FinalOutputRequest,
  NormalizeJianpuTextRequest,
  RenderJianpuSvgRequest,
  RenderJianpuTextSvgRequest,
} from '../models/types'

type WithTitle = { title?: string | null }

/**
 * The backend no longer invents a score title, so a request without one renders
 * an empty heading. Supplying the fallback here keeps it localised, which is
 * the reason the default lives on this side of the wire at all.
 */
function withDefaultTitle<T extends WithTitle>(req: T): T {
  return req.title ? req : { ...req, title: t('common.score.defaultTitle') }
}

export function usePublicationRender() {
  const gate = new RenderRequestGate()

  onScopeDispose(() => gate.dispose())

  return {
    jianpuSvg: (req: RenderJianpuSvgRequest) => gate.current((signal) => renderApi.jianpuSvg(withDefaultTitle(req), signal)),
    jianpuTextSvg: (req: RenderJianpuTextSvgRequest) => gate.current((signal) => renderApi.jianpuTextSvg(withDefaultTitle(req), signal)),
    finalOutput: (req: FinalOutputRequest) => gate.current((signal) => renderApi.finalOutput(withDefaultTitle(req), signal)),
    batchA4: (req: BatchRenderRequest) => gate.current((signal) => renderApi.batchA4(withDefaultTitle(req), signal)),
    normalizeJianpuText: (req: NormalizeJianpuTextRequest) => renderApi.normalizeJianpuText(withDefaultTitle(req)),
    cancel: () => gate.cancel(),
  }
}
