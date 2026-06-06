import { apiFetch, BASE_URL } from './client'
import type { SSEProgressEvent } from '../models/types'

export const tasksApi = {
  get(taskId: string): Promise<SSEProgressEvent> {
    return apiFetch(`/tasks/${taskId}`)
  },

  stream(
    taskId: string,
    onEvent?: (event: SSEProgressEvent) => void,
  ): Promise<SSEProgressEvent> {
    return streamTask(taskId, onEvent)
  },
}

export function streamTask(
  taskId: string,
  onEvent?: (event: SSEProgressEvent) => void,
): Promise<SSEProgressEvent> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`${BASE_URL()}/tasks/${taskId}/stream`)
    let settled = false

    function finish(callback: () => void): void {
      if (settled) return
      settled = true
      source.close()
      callback()
    }

    source.onmessage = (message: MessageEvent) => {
      const event = JSON.parse(message.data) as SSEProgressEvent
      onEvent?.(event)
      if (event.status === 'completed') {
        finish(() => resolve(event))
      } else if (event.status === 'failed') {
        finish(() => reject(new Error(event.error || event.message || '任务失败')))
      }
    }

    source.onerror = () => {
      finish(() => reject(new Error('SSE 连接中断')))
    }
  })
}
