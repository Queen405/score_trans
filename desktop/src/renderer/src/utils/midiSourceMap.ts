export interface SourceRange { start: number; end: number }
interface MeasureVisit { tick: number; endTick: number; scoreTick: number }
interface SourceOnset { scoreTick: number; scoreGroup: number; ranges: SourceRange[] }
export interface PlaybackEvent {
  id: string
  partIndex: number
  staff: string | null
  voice: string
  startTick: number
  endTick: number
  ranges: SourceRange[]
}
export interface MidiSourceMap {
  version: 1 | 2
  textHash: string | null
  measures: MeasureVisit[]
  onsets: Map<number, SourceOnset>
  events: PlaybackEvent[]
}
export interface PlaybackHighlight {
  ranges: SourceRange[]
  textHash: string | null
  focusRange: SourceRange | null
  focusEventId: string | null
}
export function emptyPlaybackHighlight(textHash: string | null = null): PlaybackHighlight {
  return { ranges: [], textHash, focusRange: null, focusEventId: null }
}
interface Marker { type: string; ticks: number; text: string }
const PREFIX = 'score-trans-playback:'
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0
function validRanges(value: unknown): value is SourceRange[] {
  return Array.isArray(value) && value.every((r) => r && integer(r.start) && integer(r.end) && r.end > r.start)
}

export function readMidiSourceMap(meta: Marker[]): MidiSourceMap | null {
  const markers = meta.filter((m) => m.type === 'marker' && m.text.startsWith(PREFIX))
  if (!markers.length) return null
  const measures: MeasureVisit[] = []
  const onsets = new Map<number, SourceOnset>()
  const events: PlaybackEvent[] = []
  const eventIds = new Set<string>()
  let version: 1 | 2 | null = null
  let textHash: string | null = null
  try {
    for (const marker of markers) {
      if (!integer(marker.ticks)) return null
      const data = JSON.parse(marker.text.slice(PREFIX.length))
      if (!data || typeof data !== 'object') return null
      if (data.kind === 'document') {
        if (version !== null || marker.ticks !== 0 || (data.version !== 1 && data.version !== 2)) return null
        if (data.source_kind !== 'text' && data.source_kind !== 'score') return null
        if (data.source_kind === 'text' && (typeof data.text_hash !== 'string' || !/^[a-f0-9]{64}$/.test(data.text_hash))) return null
        textHash = data.source_kind === 'text' ? data.text_hash : null
        version = data.version
      } else if (data.kind === 'measure') {
        if (!integer(data.score_tick) || !integer(data.end_tick) || data.end_tick <= marker.ticks) return null
        measures.push({ tick: marker.ticks, endTick: data.end_tick, scoreTick: data.score_tick })
      } else if (data.kind === 'onset') {
        if (version === null || !integer(data.score_tick) || !integer(data.score_group) || onsets.has(marker.ticks) || !validRanges(data.ranges)) return null
        onsets.set(marker.ticks, { scoreTick: data.score_tick, scoreGroup: data.score_group, ranges: data.ranges })
        if (version === 2) {
          if (!Array.isArray(data.events) || !data.events.length) return null
          for (const e of data.events) {
            if (!e || typeof e.event_id !== 'string' || !e.event_id || eventIds.has(e.event_id)) return null
            if (!integer(e.part_index) || (e.staff !== null && typeof e.staff !== 'string') || typeof e.voice !== 'string' || !e.voice) return null
            if (!integer(e.end_tick) || e.end_tick <= marker.ticks || !validRanges(e.ranges)) return null
            eventIds.add(e.event_id)
            events.push({ id: e.event_id, partIndex: e.part_index, staff: e.staff, voice: e.voice, startTick: marker.ticks, endTick: e.end_tick, ranges: e.ranges })
          }
        }
      } else return null
    }
  } catch { return null }
  if (version === null || !measures.length) return null
  measures.sort((a, b) => a.tick - b.tick)
  if (measures[0]!.tick !== 0 || measures.some((m, i) => i > 0 && measures[i - 1]!.endTick !== m.tick)) return null
  for (const [tick, onset] of onsets) {
    const visit = findVisit(measures, tick)
    if (!visit || Math.abs(onset.scoreTick - (visit.scoreTick + tick - visit.tick)) > 1) return null
  }
  if (events.some((e) => e.endTick > measures.at(-1)!.endTick)) return null
  events.sort((a, b) => a.startTick - b.startTick || a.id.localeCompare(b.id))
  return { version, textHash, measures, onsets, events }
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

/** Event intervals are indexed in performance time, including repeat occurrences. */
export class ActivePlaybackEvents {
  private starts: PlaybackEvent[]
  private ends: PlaybackEvent[]
  private active = new Map<string, PlaybackEvent>()
  private nextStart = 0
  private nextEnd = 0
  private previousTick = -1
  private highlight: PlaybackHighlight

  constructor(private readonly source: MidiSourceMap | null) {
    this.starts = source?.version === 2 ? source.events : []
    this.ends = [...this.starts].sort((a, b) => a.endTick - b.endTick)
    this.highlight = emptyPlaybackHighlight(source?.textHash ?? null)
  }

  reset(): PlaybackHighlight {
    this.active.clear()
    this.nextStart = this.nextEnd = 0
    this.previousTick = -1
    this.highlight = emptyPlaybackHighlight(this.source?.textHash ?? null)
    return this.highlight
  }

  update(tick: number, seek = false): PlaybackHighlight {
    if (!Number.isFinite(tick) || tick < 0) return this.reset()
    const rebuild = seek || tick < this.previousTick || this.previousTick < 0
    let changed = rebuild
    const added: PlaybackEvent[] = []
    if (rebuild) {
      this.active.clear()
      this.nextStart = upperEventBound(this.starts, tick, 'startTick')
      this.nextEnd = upperEventBound(this.ends, tick, 'endTick')
      for (let index = 0; index < this.nextStart; index++) {
        const event = this.starts[index]!
        if (event.endTick > tick) {
          this.active.set(event.id, event)
          added.push(event)
        }
      }
    } else {
      while (this.nextEnd < this.ends.length && this.ends[this.nextEnd]!.endTick <= tick) {
        changed = this.active.delete(this.ends[this.nextEnd++]!.id) || changed
      }
      while (this.nextStart < this.starts.length && this.starts[this.nextStart]!.startTick <= tick) {
        const event = this.starts[this.nextStart++]!
        if (event.endTick > tick) {
          this.active.set(event.id, event)
          added.push(event)
          changed = true
        }
      }
    }
    this.previousTick = tick
    if (!changed) return this.highlight

    const unique = new Map<string, SourceRange>()
    for (const event of this.active.values()) {
      for (const range of event.ranges) unique.set(`${range.start}:${range.end}`, range)
    }
    const ranges = [...unique.values()].sort((a, b) => a.start - b.start || a.end - b.end)
    const candidates = added.flatMap((event) => event.ranges.map((range) => ({ event, range })))
    candidates.sort((a, b) => b.event.startTick - a.event.startTick
      || a.range.start - b.range.start || a.range.end - b.range.end
      || a.event.id.localeCompare(b.event.id))
    const focus = candidates[0]
    this.highlight = {
      ranges,
      textHash: this.source?.textHash ?? null,
      focusRange: focus ? { ...focus.range } : ranges.length ? this.highlight.focusRange : null,
      focusEventId: focus ? focus.event.id : ranges.length ? this.highlight.focusEventId : null,
    }
    return this.highlight
  }
}

function upperEventBound(events: PlaybackEvent[], tick: number, key: 'startTick' | 'endTick'): number {
  let low = 0, high = events.length
  while (low < high) {
    const mid = (low + high) >>> 1
    if (events[mid]![key] <= tick) low = mid + 1
    else high = mid
  }
  return low
}
