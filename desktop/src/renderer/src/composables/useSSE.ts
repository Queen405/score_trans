import { ref, onUnmounted } from 'vue'
import { BASE_URL } from '../api/client'
import type { SSEProgressEvent } from '../models/types'

export function useSSE() {
  const status = ref<SSEProgressEvent['status']>('pending')
  const stage = ref('')
  const percent = ref(0)
  const message = ref('')
  const error = ref<string | null>(null)
  const result = ref<Record<string, unknown> | null>(null)
  let eventSource: EventSource | null = null

  function start(taskId: string): void {
    stop()
    eventSource = new EventSource(`${BASE_URL()}/tasks/${taskId}/stream`)

    eventSource.onmessage = (event: MessageEvent) => {
      const data: SSEProgressEvent = JSON.parse(event.data)
      status.value = data.status
      stage.value = data.stage
      percent.value = data.percent
      message.value = data.message
      if (data.error) error.value = data.error
      if (data.result) result.value = data.result
      if (data.status === 'completed' || data.status === 'failed') {
        eventSource?.close()
        eventSource = null
      }
    }

    eventSource.onerror = () => {
      error.value = 'SSE 连接中断'
      eventSource?.close()
      eventSource = null
    }
  }

  function stop(): void {
    eventSource?.close()
    eventSource = null
  }

  onUnmounted(stop)

  return { status, stage, percent, message, error, result, start, stop }
}
