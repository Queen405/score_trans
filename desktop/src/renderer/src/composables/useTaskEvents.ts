import { onMounted, onUnmounted } from 'vue'
import { BASE_URL } from '../api/client'
import { notifyHistoryUpdated } from '../utils/historyEvents'
import type { SSEProgressEvent } from '../models/types'

/**
 * Connects to the global /tasks/events SSE stream on mount.
 * When a task reaches a terminal state (completed / failed), fires
 * notifyHistoryUpdated() so that any open history panel refreshes.
 */
export function useTaskEvents() {
  let es: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function connect() {
    if (disposed) return
    try {
      const url = `${BASE_URL()}/tasks/events`
      es = new EventSource(url)
    } catch {
      // EventSource constructor failed (invalid URL etc.) — retry later
      reconnectTimer = setTimeout(connect, 5000)
      return
    }

    es.onmessage = (e: MessageEvent) => {
      let event: SSEProgressEvent
      try {
        event = JSON.parse(e.data as string)
      } catch {
        return
      }
      if (event.status === 'completed' || event.status === 'failed') {
        notifyHistoryUpdated()
      }
    }

    es.onerror = () => {
      // Auto-reconnect with back-off
      es?.close()
      es = null
      if (!disposed) {
        reconnectTimer = setTimeout(connect, 5000)
      }
    }
  }

  // Delay initial connection so the renderer can finish mounting first
  onMounted(() => {
    reconnectTimer = setTimeout(connect, 2000)
  })

  onUnmounted(() => {
    disposed = true
    es?.close()
    es = null
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  })
}
