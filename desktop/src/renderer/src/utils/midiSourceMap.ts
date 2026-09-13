export interface SourceRange { start: number; end: number }
interface MeasureVisit { tick: number; endTick: number; scoreTick: number }
interface SourceOnset { scoreTick: number; scoreGroup: number; ranges: SourceRange[] }
export interface MidiSourceMap {
  textHash: string | null
  measures: MeasureVisit[]
  onsets: Map<number, SourceOnset>
}
export interface PlaybackHighlight {
  ranges: SourceRange[]
  textHash: string | null
}
interface Marker { type: string; ticks: number; text: string }
const PREFIX = 'score-trans-playback:'
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0

export function readMidiSourceMap(meta: Marker[]): MidiSourceMap | null {
  const markers = meta.filter((m) => m.type === 'marker' && m.text.startsWith(PREFIX))
  if (!markers.length) return null
  const measures: MeasureVisit[] = []
  const onsets = new Map<number, SourceOnset>()
  let documentSeen = false
  let textHash: string | null = null
  try {
    for (const marker of markers) {
      if (!integer(marker.ticks)) return null
      const data = JSON.parse(marker.text.slice(PREFIX.length))
      if (!data || typeof data !== 'object') return null
      if (data.kind === 'document') {
        if (documentSeen || marker.ticks !== 0 || data.version !== 1) return null
        if (data.source_kind !== 'text' && data.source_kind !== 'score') return null
        if (data.source_kind === 'text' && (typeof data.text_hash !== 'string' || !/^[a-f0-9]{64}$/.test(data.text_hash))) return null
        textHash = data.source_kind === 'text' ? data.text_hash : null
        documentSeen = true
      } else if (data.kind === 'measure') {
        if (!integer(data.score_tick) || !integer(data.end_tick) || data.end_tick <= marker.ticks) return null
        measures.push({ tick: marker.ticks, endTick: data.end_tick, scoreTick: data.score_tick })
      } else if (data.kind === 'onset') {
        if (!integer(data.score_tick) || !integer(data.score_group) || onsets.has(marker.ticks) || !Array.isArray(data.ranges)) return null
        if (data.ranges.some((r: SourceRange) => !r || !integer(r.start) || !integer(r.end) || r.end <= r.start)) return null
        onsets.set(marker.ticks, { scoreTick: data.score_tick, scoreGroup: data.score_group, ranges: data.ranges })
      } else return null
    }
  } catch { return null }
  if (!documentSeen || !measures.length) return null
  measures.sort((a, b) => a.tick - b.tick)
  if (measures[0]!.tick !== 0 || measures.some((m, i) => i > 0 && measures[i - 1]!.endTick !== m.tick)) return null
  for (const [tick, onset] of onsets) {
    const visit = findVisit(measures, tick)
    if (!visit || Math.abs(onset.scoreTick - (visit.scoreTick + tick - visit.tick)) > 1) return null
  }
  return { textHash, measures, onsets }
}

function findVisit(measures: MeasureVisit[], tick: number): MeasureVisit | null {
  let low = 0, high = measures.length
  while (low < high) {
    const mid = (low + high) >>> 1
    if (measures[mid]!.tick <= tick) low = mid + 1
    else high = mid
  }
  const visit = measures[low - 1]
  return visit && tick < visit.endTick ? visit : null
}

export function sourcePlaybackPosition(map: MidiSourceMap | null, tick: number, onsetTick: number, ppq: number) {
  const visit = map && Number.isFinite(tick) && tick >= 0 ? findVisit(map.measures, tick) : null
  const onset = visit ? map!.onsets.get(onsetTick) : undefined
  return {
    position: { tick: visit ? visit.scoreTick + tick - visit.tick : -1, onsetTick: onset?.scoreTick ?? -1, ppq },
    groupIndex: onset?.scoreGroup ?? -1,
    highlight: { ranges: onset?.ranges ?? [], textHash: map?.textHash ?? null } satisfies PlaybackHighlight,
  }
}

export async function playbackTextHash(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function sourceRangeSpans(text: string, ranges: SourceRange[]) {
  const lines = text.split('\n')
  const spans: Array<{ line: number; startColumn: number; endColumn: number }> = []
  let offset = 0
  for (const [line, content] of lines.entries()) {
    const length = content.endsWith('\r') ? content.length - 1 : content.length
    for (const range of ranges) {
      if (!integer(range.start) || !integer(range.end) || range.end > text.length || range.end <= range.start) continue
      const start = Math.max(offset, range.start), end = Math.min(offset + length, range.end)
      if (end > start) spans.push({ line, startColumn: start - offset, endColumn: end - offset })
    }
    offset += content.length + 1
  }
  return spans
}
