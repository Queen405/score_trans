export interface PlaybackPosition { tick: number; onsetTick: number; ppq: number }
export interface PlaybackRange { start: number; end: number; ppq: number }

export function readPlaybackRange(svg: Element): PlaybackRange | null {
  if (svg.getAttribute('data-playback-version') !== '1') return null
  const values = ['data-playback-start-tick', 'data-playback-end-tick', 'data-playback-ppq']
    .map((key) => svg.getAttribute(key))
  if (values.some((value) => value === null || value.trim() === '')) return null
  const [start, end, ppq] = values.map(Number)
  if (![start, end, ppq].every(Number.isFinite) || start! < 0 || end! <= start! || ppq! <= 0) return null
  return { start: start!, end: end!, ppq: ppq! }
}

export function playbackPage(ranges: Array<PlaybackRange | null>, position: PlaybackPosition): number | null {
  if (position.tick < 0 || position.ppq <= 0) return null
  const index = ranges.findIndex((range) => {
    if (!range) return false
    const tick = position.tick * range.ppq / position.ppq
    return tick >= range.start && tick < range.end
  })
  return index < 0 ? null : index
}

export function playbackTargets(svg: SVGSVGElement, position: PlaybackPosition): SVGGElement[] {
  const range = readPlaybackRange(svg)
  if (!range || position.onsetTick < 0 || position.ppq <= 0) return []
  const tick = Math.round(position.onsetTick * range.ppq / position.ppq)
  if (tick < range.start || tick >= range.end) return []
  return Array.from(svg.querySelectorAll<SVGGElement>(`.playback-note[data-playback-tick="${tick}"]`))
}
