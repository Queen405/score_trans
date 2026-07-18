export const HISTORY_UPDATED_EVENT = 'score-trans:history-updated'
export const HISTORY_PAGE_PATCHED_EVENT = 'score-trans:history-page-patched'

export interface HistoryPagePatchDetail {
  id: number
  patch: {
    task_id?: string
    musicxml_file_id?: string
    jianpu_text?: string
    ocr_text?: string
    svg_file_id?: string
    status?: string
    error_message?: string
  }
}

export function notifyHistoryUpdated(): void {
  window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT))
}

export function notifyHistoryPagePatched(detail: HistoryPagePatchDetail): void {
  window.dispatchEvent(new CustomEvent<HistoryPagePatchDetail>(HISTORY_PAGE_PATCHED_EVENT, { detail }))
}

export function listenHistoryUpdated(callback: () => void | Promise<void>, debounceMs = 300): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  const handler = (): void => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      void callback()
    }, debounceMs)
  }
  window.addEventListener(HISTORY_UPDATED_EVENT, handler)
  return () => {
    if (timer) clearTimeout(timer)
    window.removeEventListener(HISTORY_UPDATED_EVENT, handler)
  }
}

export function listenHistoryPagePatched(
  callback: (detail: HistoryPagePatchDetail) => void,
): () => void {
  const handler = (event: Event): void => {
    callback((event as CustomEvent<HistoryPagePatchDetail>).detail)
  }
  window.addEventListener(HISTORY_PAGE_PATCHED_EVENT, handler)
  return () => {
    window.removeEventListener(HISTORY_PAGE_PATCHED_EVENT, handler)
  }
}
