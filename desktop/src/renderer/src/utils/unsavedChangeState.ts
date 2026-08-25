export type UserChangeKind = 'jianpu' | 'ocr' | 'attachments'

export interface ChangeRevision {
  jianpu: number
  ocr: number
  attachments: number
}

export interface BatchRevisionState {
  edited: ChangeRevision
  saved: ChangeRevision
}

const ALL_CHANGE_KINDS: readonly UserChangeKind[] = [
  'jianpu',
  'ocr',
  'attachments',
]

function emptyRevision(): ChangeRevision {
  return { jianpu: 0, ocr: 0, attachments: 0 }
}

export function createRevisionState(): BatchRevisionState {
  return { edited: emptyRevision(), saved: emptyRevision() }
}

export function markEdited(
  state: BatchRevisionState,
  kind: UserChangeKind,
): BatchRevisionState {
  return {
    edited: {
      ...state.edited,
      [kind]: state.edited[kind] + 1,
    },
    saved: { ...state.saved },
  }
}

export function captureEditedRevision(state: BatchRevisionState): ChangeRevision {
  return { ...state.edited }
}

export function acknowledgeRevision(
  state: BatchRevisionState,
  captured: ChangeRevision,
  kinds: readonly UserChangeKind[] = ALL_CHANGE_KINDS,
): BatchRevisionState {
  const saved = { ...state.saved }
  for (const kind of kinds) {
    saved[kind] = Math.max(saved[kind], captured[kind])
  }
  return { edited: { ...state.edited }, saved }
}

export function hasUnsavedChanges(state: BatchRevisionState): boolean {
  return ALL_CHANGE_KINDS.some((kind) => state.edited[kind] > state.saved[kind])
}

export function hasUnsavedChangeKind(
  state: BatchRevisionState,
  kind: UserChangeKind,
): boolean {
  return state.edited[kind] > state.saved[kind]
}
