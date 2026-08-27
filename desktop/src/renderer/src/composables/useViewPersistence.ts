export interface ViewState {
  scale: number
  tx: number
  ty: number
}

export interface EditorScrollState {
  scrollTop: number
  scrollLeft: number
}

const ZOOM_KEY_PREFIX = 'score-trans.view-state.zoom.'
const PAGE_KEY_PREFIX = 'score-trans.view-state.render-page.'
const EDITOR_SCROLL_PREFIX = 'score-trans.view-state.editor-scroll.'

function sessionGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function sessionSet(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value)
  } catch {
    // sessionStorage may be unavailable (private mode / disabled); ignore.
  }
}

function sessionRemove(key: string): void {
  try {
    sessionStorage.removeItem(key)
  } catch {
    // ignore
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

export function loadViewState(svgFileId: string): ViewState | null {
  if (!svgFileId) return null
  const raw = sessionGet(`${ZOOM_KEY_PREFIX}${svgFileId}`)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<ViewState>
    if (
      isFiniteNumber(parsed.scale)
      && isFiniteNumber(parsed.tx)
      && isFiniteNumber(parsed.ty)
    ) {
      return { scale: parsed.scale!, tx: parsed.tx!, ty: parsed.ty! }
    }
  } catch {
    // corrupt entry; drop it so the next save can replace it
  }
  sessionRemove(`${ZOOM_KEY_PREFIX}${svgFileId}`)
  return null
}

export function saveViewState(svgFileId: string, state: ViewState): void {
  if (!svgFileId) return
  if (!isFiniteNumber(state.scale) || !isFiniteNumber(state.tx) || !isFiniteNumber(state.ty)) {
    return
  }
  sessionSet(`${ZOOM_KEY_PREFIX}${svgFileId}`, JSON.stringify(state))
}

export function loadRenderPageIndex(batchId: string | null): number | null {
  if (!batchId) return null
  const raw = sessionGet(`${PAGE_KEY_PREFIX}${batchId}`)
  if (raw == null) return null
  const parsed = Number.parseInt(raw, 10)
  if (!Number.isInteger(parsed) || parsed < 0) {
    sessionRemove(`${PAGE_KEY_PREFIX}${batchId}`)
    return null
  }
  return parsed
}

export function saveRenderPageIndex(batchId: string | null, index: number): void {
  if (!batchId || !Number.isInteger(index) || index < 0) return
  sessionSet(`${PAGE_KEY_PREFIX}${batchId}`, String(index))
}

export function loadEditorScroll(key: string | null): EditorScrollState | null {
  if (!key) return null
  const raw = sessionGet(`${EDITOR_SCROLL_PREFIX}${key}`)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<EditorScrollState>
    if (isFiniteNumber(parsed.scrollTop) && isFiniteNumber(parsed.scrollLeft)) {
      return { scrollTop: parsed.scrollTop!, scrollLeft: parsed.scrollLeft! }
    }
  } catch {
    // corrupt entry; drop it
  }
  sessionRemove(`${EDITOR_SCROLL_PREFIX}${key}`)
  return null
}

export function saveEditorScroll(key: string | null, state: EditorScrollState): void {
  if (!key) return
  if (!isFiniteNumber(state.scrollTop) || !isFiniteNumber(state.scrollLeft)) return
  sessionSet(`${EDITOR_SCROLL_PREFIX}${key}`, JSON.stringify(state))
}
