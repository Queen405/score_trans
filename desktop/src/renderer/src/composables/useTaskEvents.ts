import { onMounted, onUnmounted } from 'vue'
import { getBaseURL } from '../api/client'
import { notifyHistoryUpdated } from '../utils/historyEvents'
import type { SSEProgressEvent } from '../models/types'

/**
 * Connects to the global /tasks/events SSE stream on mount.
 * When a task reaches a terminal state (completed / failed), fires
 * notifyHistoryUpdated() so that any open history panel refreshes.
 *
 * This replaces the need for per-task SSE reconnection after page refresh
 * and provides real-time cross-component task awareness.
 */
export function useTaskEvents() {
  let es: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const base = getBaseURL()
    es = new EventSource(`${base}/tasks/events`)

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
      reconnectTimer = setTimeout(connect, 5000)
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    es?.close()
    es = null
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  })
}
