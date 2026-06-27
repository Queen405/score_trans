import type { TaskPageInput, TaskPageStatus } from '../stores/task'

interface LiveRecognitionState {
  historyPageId: number
  taskId: string
  status: TaskPageStatus
  progressPercent: number
  progressMessage: string
  errorMessage: string
}

const pageToHistory = new Map<string, number>()
const statesByHistory = new Map<number, LiveRecognitionState>()

export function registerLiveRecognitionPage(pageId: string, historyPageId: number | null): void {
  if (!historyPageId) return
  pageToHistory.set(pageId, historyPageId)
  if (!statesByHistory.has(historyPageId)) {
    statesByHistory.set(historyPageId, {
      historyPageId,
      taskId: '',
      status: 'processing',
      progressPercent: 0,
      progressMessage: '',
      errorMessage: '',
    })
  }
}

export function getLiveRecognitionHistoryPageId(pageId: string): number | null {
  return pageToHistory.get(pageId) ?? null
}

export function updateLiveRecognitionPage(
  pageId: string,
  patch: Partial<Omit<LiveRecognitionState, 'historyPageId'>>,
): void {
  const historyPageId = pageToHistory.get(pageId)
  if (!historyPageId) return
  const current = statesByHistory.get(historyPageId) ?? {
    historyPageId,
    taskId: '',
    status: 'processing' as TaskPageStatus,
    progressPercent: 0,
    progressMessage: '',
    errorMessage: '',
  }
  statesByHistory.set(historyPageId, { ...current, ...patch })
}

export function clearLiveRecognitionPage(pageId: string): void {
  const historyPageId = pageToHistory.get(pageId)
  pageToHistory.delete(pageId)
  if (historyPageId) {
    statesByHistory.delete(historyPageId)
  }
}

export function liveRecognitionTaskPatch(
  historyPageId: number,
  historyStatus: string,
): Partial<Pick<TaskPageInput, 'taskId' | 'status' | 'progressPercent' | 'progressMessage' | 'errorMessage'>> {
  if (historyStatus !== 'processing' && historyStatus !== 'pending') return {}
  const state = statesByHistory.get(historyPageId)
  if (!state) return {}
  const patch: Partial<Pick<TaskPageInput, 'taskId' | 'status' | 'progressPercent' | 'progressMessage' | 'errorMessage'>> = {
    status: state.status,
    progressPercent: state.progressPercent,
    progressMessage: state.progressMessage,
    errorMessage: state.errorMessage,
  }
  if (state.taskId) patch.taskId = state.taskId
  return patch
}
