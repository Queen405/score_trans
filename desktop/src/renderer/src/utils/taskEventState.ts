export type TaskEventDisposition = 'progress' | 'completed' | 'failed'

export function taskEventDisposition(status: string): TaskEventDisposition {
  if (status === 'completed') return 'completed'
  if (status === 'failed') return 'failed'
  return 'progress'
}

export function dispatchTaskProgress<T extends { status: string }>(
  event: T,
  onProgress?: (event: T) => void,
): TaskEventDisposition {
  const disposition = taskEventDisposition(event.status)
  if (disposition !== 'progress') return disposition
  onProgress?.(event)
  return disposition
}
