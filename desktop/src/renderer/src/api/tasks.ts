import { apiFetch, BASE_URL } from './client'
import type { SSEProgressEvent } from '../models/types'
import { dispatchTaskProgress } from '../utils/taskEventState'

const TASK_POLL_INTERVAL_MS = 2_000
const MAX_CONSECUTIVE_POLL_FAILURES = 30

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
    let polling = false
    let consecutivePollFailures = 0
    const pollTimer = window.setInterval(() => {
      void pollTask()
    }, TASK_POLL_INTERVAL_MS)

    function finish(callback: () => void): void {
      if (settled) return
      settled = true
      window.clearInterval(pollTimer)
      source.close()
      callback()
    }

    function handleEvent(event: SSEProgressEvent): void {
      const disposition = dispatchTaskProgress(event, (progressEvent) => {
        try {
          onEvent?.(progressEvent)
        } catch (error) {
          console.error('任务进度回调失败', error)
        }
      })
      if (disposition === 'completed') {
        finish(() => resolve(event))
      } else if (disposition === 'failed') {
        finish(() => reject(new Error(event.error || event.message || '任务失败')))
      }
    }

    async function pollTask(): Promise<void> {
      if (settled || polling) return
      polling = true
      try {
        const event = await apiFetch<SSEProgressEvent>(`/tasks/${taskId}`)
        consecutivePollFailures = 0
        handleEvent(event)
      } catch (error) {
        consecutivePollFailures += 1
        if (consecutivePollFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
          const message = error instanceof Error ? error.message : '无法查询任务状态'
          finish(() => reject(new Error(`任务状态查询失败：${message}`)))
        }
      } finally {
        polling = false
      }
    }

    source.onmessage = (message: MessageEvent) => {
      try {
        handleEvent(JSON.parse(message.data) as SSEProgressEvent)
      } catch {
        void pollTask()
      }
    }

    source.onerror = () => {
      void pollTask()
    }

    void pollTask()
  })
}
