export const HISTORY_UPDATED_EVENT = 'score-trans:history-updated'

export function notifyHistoryUpdated(): void {
  window.dispatchEvent(new CustomEvent(HISTORY_UPDATED_EVENT))
}

export function listenHistoryUpdated(callback: () => void | Promise<void>): () => void {
  const handler = (): void => {
    void callback()
  }
  window.addEventListener(HISTORY_UPDATED_EVENT, handler)
  return () => window.removeEventListener(HISTORY_UPDATED_EVENT, handler)
}
