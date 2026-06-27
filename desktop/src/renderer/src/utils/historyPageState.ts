export type HistoryPageOpenAction = 'choose' | 'restore' | 'wait'

export function historyPageOpenAction(status: string): HistoryPageOpenAction {
  if (status === 'waiting') return 'choose'
  if (status === 'processing' || status === 'pending') return 'wait'
  return 'restore'
}
