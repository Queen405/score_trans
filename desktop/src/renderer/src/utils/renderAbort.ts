export function isRenderAborted(error: unknown): boolean {
  if (typeof error !== 'object' || error === null) return false

  const candidate = error as { name?: unknown; code?: unknown }
  return candidate.name === 'AbortError' || candidate.code === 'aborted'
}
