export interface HorizontalScrollRequest {
  scrollLeft: number
  clientWidth: number
  paddingLeft: number
  charWidth: number
  startColumn: number
  endColumn: number
}

export function horizontalScrollIntoView(request: HorizontalScrollRequest): number {
  const {
    scrollLeft,
    clientWidth,
    paddingLeft,
    charWidth,
    startColumn,
    endColumn,
  } = request
  const left = paddingLeft + startColumn * charWidth
  const right = paddingLeft + Math.max(startColumn + 1, endColumn) * charWidth
  const margin = charWidth * 2

  if (left < scrollLeft) return Math.max(0, left - margin)
  if (right > scrollLeft + clientWidth) {
    return Math.max(0, right - clientWidth + margin)
  }
  return scrollLeft
}
