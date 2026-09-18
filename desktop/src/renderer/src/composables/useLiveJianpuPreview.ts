import { ref } from 'vue'
import { t } from '../i18n'
import { renderApi } from '../api/render'
import type { LiveJianpuSvgRequest, LiveJianpuSvgResponse, SyntaxDiagnostic } from '../models/types'
import type { ApiResult } from '../api/client'
import { createRequestEpoch } from '../utils/asyncCoordination'
import { isRenderAborted } from '../utils/renderAbort'

interface PreviewInput {
  documentId: string | null
  enabled: boolean
  request: LiveJianpuSvgRequest
}

type PreviewRequest = (
  request: LiveJianpuSvgRequest,
  signal: AbortSignal,
) => Promise<ApiResult<LiveJianpuSvgResponse>>

export function useLiveJianpuPreview(request: PreviewRequest = renderApi.liveJianpuSvg) {
  const svg = ref('')
  const error = ref('')
  const warnings = ref<SyntaxDiagnostic[]>([])
  const loading = ref(false)
  const epoch = createRequestEpoch()
  let timer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null
  let documentId: string | null | undefined
  let disposed = false

  function invalidate(): void {
    epoch.invalidate()
    if (timer !== null) clearTimeout(timer)
    timer = null
    controller?.abort()
    controller = null
  }

  function clear(): void {
    svg.value = ''
    error.value = ''
    warnings.value = []
    loading.value = false
  }

  function update(input: PreviewInput): void {
    if (disposed) return
    invalidate()
    if (input.documentId !== documentId) clear()
    documentId = input.documentId
    if (!input.enabled || !input.request.jianpu_text.trim()) {
      clear()
      return
    }
    const generation = epoch.begin()
    const snapshot = { ...input.request }
    error.value = ''
    warnings.value = []
    loading.value = true
    timer = setTimeout(() => {
      timer = null
      const activeController = new AbortController()
      controller = activeController
      void run(snapshot, activeController, generation)
    }, 150)
  }

  async function run(snapshot: LiveJianpuSvgRequest, activeController: AbortController, generation: number): Promise<void> {
    try {
      const result = await request(snapshot, activeController.signal)
      if (!epoch.isCurrent(generation)) return
      if (result.data) {
        svg.value = result.data.svg
        warnings.value = result.data.warnings ?? []
        error.value = ''
      } else if (result.error && !isRenderAborted(result.error)) {
        error.value = result.error.message
      }
    } catch (cause) {
      if (epoch.isCurrent(generation) && !isRenderAborted(cause)) {
        error.value = cause instanceof Error ? cause.message : t('runtime.preview.liveFailed')
      }
    } finally {
      if (epoch.isCurrent(generation)) {
        loading.value = false
        controller = null
      }
    }
  }

  function dispose(): void {
    disposed = true
    invalidate()
    clear()
  }

  return { svg, error, warnings, loading, update, dispose }
}
