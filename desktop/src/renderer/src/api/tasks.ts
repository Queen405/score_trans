import {
  ApiError,
  authenticatedFetch,
  apiFetch,
  BASE_URL,
  requireData,
  toApiResult,
  type ApiResult,
} from './client'
import type { SSEProgressEvent } from '../models/types'
import { dispatchTaskProgress } from '../utils/taskEventState'
import { t } from '../i18n'

const TASK_POLL_INTERVAL_MS = 2_000
const MAX_CONSECUTIVE_POLL_FAILURES = 30

export const tasksApi = {
  get(taskId: string): Promise<ApiResult<SSEProgressEvent>> {
    return apiFetch(`/tasks/${taskId}`)
  },

  stream(
    taskId: string,
    onEvent?: (event: SSEProgressEvent) => void,
    signal?: AbortSignal,
  ): Promise<ApiResult<SSEProgressEvent>> {
    return toApiResult(streamTask(taskId, onEvent, signal))
  },
}

function streamTask(
  taskId: string,
  onEvent?: (event: SSEProgressEvent) => void,
  signal?: AbortSignal,
): Promise<SSEProgressEvent> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController()
    let settled = false
    let polling = false
    let consecutivePollFailures = 0
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let reader: ReadableStreamDefaultReader<Uint8Array> | null = null

    function finish(callback: () => void): void {
      if (settled) return
      settled = true
      if (pollTimer !== null) clearInterval(pollTimer)
      signal?.removeEventListener('abort', cancel)
      controller.abort()
      callback()
    }

    function cancel(): void {
      if (settled) return
      void reader?.cancel()
      finish(() => reject(new ApiError(t('runtime.api.streamCancelled'))))
    }

    if (signal?.aborted) {
      cancel()
      return
    }
    signal?.addEventListener('abort', cancel, { once: true })

    function handleEvent(event: SSEProgressEvent): void {
      const disposition = dispatchTaskProgress(event, (progressEvent) => {
        try {
          onEvent?.(progressEvent)
        } catch (error) {
          console.error(t('runtime.api.progressCallbackFailed'), error)
        }
      })
      if (disposition === 'completed') {
        finish(() => resolve(event))
      } else if (disposition === 'failed') {
        finish(() => reject(new Error(event.error || event.message || t('runtime.api.taskFailed'))))
      }
    }

    async function pollTask(): Promise<void> {
      if (settled || polling) return
      polling = true
      try {
        const event = await requireData(apiFetch<SSEProgressEvent>(`/tasks/${taskId}`, {
          signal: controller.signal,
        }))
        consecutivePollFailures = 0
        handleEvent(event)
      } catch (error) {
        consecutivePollFailures += 1
        if (consecutivePollFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
          const message = error instanceof Error ? error.message : t('runtime.api.queryStatusUnavailable')
          finish(() => reject(new Error(t('runtime.api.statusQueryFailed', { message }))))
        }
      } finally {
        polling = false
      }
    }

    async function consumeStream(): Promise<void> {
      try {
        const response = await authenticatedFetch(
          `${BASE_URL()}/tasks/${taskId}/stream`,
          {
            headers: { Accept: 'text/event-stream' },
            cache: 'no-store',
            signal: controller.signal,
          },
        )
        if (!response.ok) {
          throw new ApiError(`HTTP ${response.status}`)
        }
        if (!response.body) {
          throw new ApiError(t('runtime.api.streamUnsupported'))
        }

        reader = response.body.getReader()
        if (settled) {
          await reader.cancel()
          return
        }
        const decoder = new TextDecoder()
        let buffer = ''
        while (!settled) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split(/\r?\n\r?\n/)
          buffer = blocks.pop() ?? ''
          for (const block of blocks) {
            const event = parseTaskEvent(block)
            if (event) handleEvent(event)
          }
        }
        if (!settled && buffer.trim()) {
          const event = parseTaskEvent(buffer)
          if (event) handleEvent(event)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          console.warn(t('runtime.api.streamInterrupted'), error)
          void pollTask()
        }
      }
    }

    pollTimer = setInterval(() => {
      void pollTask()
    }, TASK_POLL_INTERVAL_MS)
    void consumeStream()
    void pollTask()
  })
}

function parseTaskEvent(block: string): SSEProgressEvent | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trim())
    .join('\n')
  if (!data) return null
  try {
    return JSON.parse(data) as SSEProgressEvent
  } catch {
    return null
  }
}
