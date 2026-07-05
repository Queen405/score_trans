import { parseJianpuPageMarker, parseJianpuPageSections } from './jianpuPageSections'

export interface JianpuNoteSpan {
  index: number
  line: number
  startColumn: number
  endColumn: number
  token: string
}

export const TOKEN_PATTERN = /\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+/g
const DURATION_PREFIX_PATTERN = /^(?:[whqs]|d+)/
const MICROTONAL_PREFIX_PATTERN = /^(?:qs|qf)/
const PITCH_PATTERN = /^(?:(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[1-7][',]*|[1-7][',]*[#b])$/
const TUPLET_PART_PATTERN =
  /(?:[whqs]|d+)?(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[0-7][',]*[#b]?/g
export const TUPLET_RATIO_PATTERN = /^\d+\s*:\s*\d+\s*;/
const PART_MARKER_PATTERN = /^\s*\/\/\s*@part\s+\d+/

// ── Fraction utilities (exact arithmetic to match backend Fraction) ──

interface Frac {
  num: number
  den: number
}

function gcd(a: number, b: number): number {
  a = Math.abs(a)
  b = Math.abs(b)
  while (b) {
    const t = b
    b = a % b
    a = t
  }
  return a || 1
}

function lcm(a: number, b: number): number {
  return Math.abs(a * b) / gcd(a, b)
}

function frac(num: number, den: number = 1): Frac {
  if (den === 0) den = 1
  if (den < 0) {
    num = -num
    den = -den
  }
  const g = gcd(num, den)
  return { num: num / g, den: den / g }
}

function fracAdd(a: Frac, b: Frac): Frac {
  return frac(a.num * b.den + b.num * a.den, a.den * b.den)
}

function fracMul(a: Frac, b: Frac): Frac {
  return frac(a.num * b.num, a.den * b.den)
}

function fracLt(a: Frac, b: Frac): boolean {
  return a.num * b.den < b.num * a.den
}

function fracKey(f: Frac): string {
  return `${f.num}/${f.den}`
}

// ── Duration computation (mirrors backend token_duration / jianpu_tokens.py) ──

const DURATION_PREFIX_MAP: Array<[string, Frac]> = [
  ['ddddd', frac(1, 128)],
  ['dddd', frac(1, 64)],
  ['ddd', frac(1, 32)],
  ['dd', frac(1, 16)],
  ['d', frac(1, 8)],
  ['w', frac(4, 1)],
  ['h', frac(2, 1)],
  ['q', frac(1, 2)],
  ['s', frac(1, 4)],
]

const ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION = ['tqf', 'tqs', 'qf', 'qs']

function consumeDurationPrefix(token: string): [Frac, string] {
  if (ACCIDENTAL_PREFIXES_STARTING_WITH_DURATION.some((p) => token.startsWith(p))) {
    return [frac(1), token]
  }
  for (const [prefix, dur] of DURATION_PREFIX_MAP) {
    if (token.startsWith(prefix)) {
      return [dur, token.slice(prefix.length)]
    }
  }
  return [frac(1), token]
}

function consumeDurationSuffix(base: Frac, token: string): Frac {
  let work = token
  let extensions = 0
  while (work.endsWith('-')) {
    extensions++
    work = work.slice(0, -1)
  }
  let dots = 0
  while (work.endsWith('.')) {
    dots++
    work = work.slice(0, -1)
  }
  const dottedMultiplier = frac(2 ** (dots + 1) - 1, 2 ** dots)
  return fracAdd(fracMul(base, dottedMultiplier), frac(extensions))
}

function tokenDuration(token: string): Frac {
  let work = token.trim()
  while (work.startsWith('(')) work = work.slice(1)
  while (work.endsWith(')')) work = work.slice(0, -1)
  if (work.startsWith('~')) work = work.slice(1)
  if (work.endsWith('~')) work = work.slice(0, -1)

  if (work.startsWith('[') && work.endsWith(']')) {
    const parts = work.slice(1, -1).split('+').map((p) => p.trim()).filter(Boolean)
    if (parts.length === 0) return frac(1)
    let min = tokenDuration(parts[0])
    for (let i = 1; i < parts.length; i++) {
      const d = tokenDuration(parts[i])
      if (fracLt(d, min)) min = d
    }
    return min
  }

  const [base, afterPrefix] = consumeDurationPrefix(work)
  return consumeDurationSuffix(base, afterPrefix)
}

function hasDurationPrefix(token: string): boolean {
  const stripped = token.trim().replace(/^[()~]+|[()~]+$/g, '')
  const [, afterPrefix] = consumeDurationPrefix(stripped)
  return afterPrefix !== stripped
}

function tupletNormalNotes(actualNotes: number): number {
  let normal = 1
  while (normal * 2 <= actualNotes) {
    normal *= 2
  }
  return Math.max(1, normal)
}

function tupletDurationUnitCount(durations: Frac[]): number {
  if (durations.length === 0) return 0
  let commonDen = 1
  for (const d of durations) {
    commonDen = lcm(commonDen, d.den)
  }
  const scaled = durations.map((d) => d.num * (commonDen / d.den))
  let unit = 0
  for (const v of scaled) {
    unit = gcd(unit, v)
  }
  return scaled.reduce((sum, v) => sum + v / unit, 0)
}

function tupletNoteDurations(token: string): Frac[] {
  const body = token.slice(1, -1).trim()
  let remaining = body
  let explicitRatio: [number, number] | null = null
  const ratioMatch = remaining.match(/^(\d+)\s*:\s*(\d+)\s*;/)
  if (ratioMatch) {
    explicitRatio = [Number(ratioMatch[1]), Number(ratioMatch[2])]
    remaining = remaining.slice(ratioMatch[0].length).trim()
  }

  let parts: string[]
  if (/\s/.test(remaining)) {
    parts = remaining.split(/\s+/).filter(Boolean)
  } else {
    parts = Array.from(remaining.matchAll(TUPLET_PART_PATTERN), (m) => m[0])
  }
  if (parts.length === 0) return []

  const baseDurations = parts.map((p) => tokenDuration(p))
  const hasExplicitDurations = parts.some((p) => hasDurationPrefix(p))

  let actualCount: number
  let normalCount: number
  if (explicitRatio) {
    actualCount = explicitRatio[0]
    normalCount = explicitRatio[1]
  } else if (hasExplicitDurations) {
    actualCount = tupletDurationUnitCount(baseDurations)
    normalCount = tupletNormalNotes(actualCount)
  } else {
    actualCount = parts.length
    normalCount = tupletNormalNotes(actualCount)
  }

  if (explicitRatio || hasExplicitDurations) {
    const multiplier = frac(normalCount, actualCount)
    return baseDurations.map((d) => fracMul(d, multiplier))
  }
  return baseDurations.map(() => frac(1, actualCount))
}

// ── Note span discovery ──

function hasPartMarkers(text: string): boolean {
  return text.split('\n').some((line) => PART_MARKER_PATTERN.test(line))
}

export function findJianpuNoteSpans(text: string): JianpuNoteSpan[] {
  if (hasPartMarkers(text)) {
    return findTimedNoteSpans(text)
  }
  return findSequentialNoteSpans(text)
}

function findSequentialNoteSpans(text: string): JianpuNoteSpan[] {
  const spans: JianpuNoteSpan[] = []
  let noteIndex = 0

  text.split('\n').forEach((line, lineIndex) => {
    const code = stripInlineComment(line)
    if (isMetadataLine(code)) return

    for (const match of code.matchAll(TOKEN_PATTERN)) {
      const token = match[0]
      if (isTupletToken(token)) {
        for (const part of tupletPartSpans(token, match.index ?? 0)) {
          if (!isPlayableToken(part.token)) continue
          spans.push({
            index: noteIndex,
            line: lineIndex,
            startColumn: part.startColumn,
            endColumn: part.endColumn,
            token: part.token,
          })
          noteIndex += 1
        }
        continue
      }
      if (!isPlayableToken(token)) continue

      const startColumn = match.index ?? 0
      spans.push({
        index: noteIndex,
        line: lineIndex,
        startColumn,
        endColumn: startColumn + token.length,
        token,
      })
      noteIndex += 1
    }
  })

  return spans
}

interface RawTimedSpan {
  line: number
  startColumn: number
  endColumn: number
  token: string
  measureIndex: number
  startBeat: Frac
}

function findTimedNoteSpans(text: string): JianpuNoteSpan[] {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')

  interface PartState {
    measureIndex: number
    beatPosition: Frac
  }
  const partStates: PartState[] = []
  let currentPartOrdinal = -1

  const rawSpans: RawTimedSpan[] = []

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const rawLine = lines[lineIdx]
    const code = stripInlineComment(rawLine)

    if (parseJianpuPageMarker(rawLine)) {
      currentPartOrdinal = -1
      continue
    }

    if (PART_MARKER_PATTERN.test(rawLine)) {
      currentPartOrdinal++
      if (!partStates[currentPartOrdinal]) {
        partStates[currentPartOrdinal] = { measureIndex: 0, beatPosition: frac(0) }
      }
      continue
    }

    if (isMetadataLine(code)) continue

    let partOrdinal = currentPartOrdinal
    if (partOrdinal < 0) {
      partOrdinal = 0
      if (!partStates[0]) partStates[0] = { measureIndex: 0, beatPosition: frac(0) }
    }
    const state = partStates[partOrdinal]
    if (!state) continue

    for (const match of code.matchAll(TOKEN_PATTERN)) {
      const token = match[0]
      const startColumn = match.index ?? 0

      if (token === '|' || token === '||' || token === '|:' || token === ':|') {
        state.measureIndex++
        state.beatPosition = frac(0)
        continue
      }

      if (isTupletToken(token)) {
        const durations = tupletNoteDurations(token)
        const partSpans = tupletPartSpans(token, startColumn)
        for (let i = 0; i < partSpans.length && i < durations.length; i++) {
          const part = partSpans[i]
          if (!isPlayableToken(part.token)) {
            state.beatPosition = fracAdd(state.beatPosition, durations[i])
            continue
          }
          rawSpans.push({
            line: lineIdx,
            startColumn: part.startColumn,
            endColumn: part.endColumn,
            token: part.token,
            measureIndex: state.measureIndex,
            startBeat: state.beatPosition,
          })
          state.beatPosition = fracAdd(state.beatPosition, durations[i])
        }
        continue
      }

      if (token === '-') {
        state.beatPosition = fracAdd(state.beatPosition, frac(1))
        continue
      }

      if (isRestToken(token)) {
        state.beatPosition = fracAdd(state.beatPosition, tokenDuration(token))
        continue
      }

      if (!isPlayableToken(token)) continue

      const dur = tokenDuration(token)
      rawSpans.push({
        line: lineIdx,
        startColumn,
        endColumn: startColumn + token.length,
        token,
        measureIndex: state.measureIndex,
        startBeat: state.beatPosition,
      })
      state.beatPosition = fracAdd(state.beatPosition, dur)
    }
  }

  const maxMeasure = rawSpans.reduce((max, s) => Math.max(max, s.measureIndex), 0)
  const spans: JianpuNoteSpan[] = []
  let playbackIndex = -1

  for (let measureIdx = 0; measureIdx <= maxMeasure; measureIdx++) {
    const measureNotes = rawSpans
      .filter((s) => s.measureIndex === measureIdx)
      .sort((a, b) => {
        if (fracLt(a.startBeat, b.startBeat)) return -1
        if (fracLt(b.startBeat, a.startBeat)) return 1
        return 0
      })

    let currentStart: string | null = null
    for (const note of measureNotes) {
      const key = fracKey(note.startBeat)
      if (currentStart === null || key !== currentStart) {
        playbackIndex++
        currentStart = key
      }
      spans.push({
        index: playbackIndex,
        line: note.line,
        startColumn: note.startColumn,
        endColumn: note.endColumn,
        token: note.token,
      })
    }
  }

  spans.sort((a, b) => {
    if (a.line !== b.line) return a.line - b.line
    return a.startColumn - b.startColumn
  })

  return spans
}

function isRestToken(token: string): boolean {
  let work = stripEventDecorations(token)
  while (work.endsWith('.')) work = work.slice(0, -1)
  return work === '0'
}

function isTupletToken(token: string): boolean {
  return token.startsWith('$') && token.endsWith('$') && token.length > 2
}

function tupletPartSpans(
  token: string,
  tokenStartColumn: number,
): Array<{ token: string; startColumn: number; endColumn: number }> {
  const body = token.slice(1, -1)
  const ratioLength = body.match(TUPLET_RATIO_PATTERN)?.[0].length ?? 0
  const eventBody = body.slice(ratioLength)
  if (/\s/.test(eventBody)) {
    return Array.from(eventBody.matchAll(/\S+/g), (match) => {
      const part = match[0]
      const startColumn = tokenStartColumn + 1 + ratioLength + (match.index ?? 0)
      return { token: part, startColumn, endColumn: startColumn + part.length }
    })
  }
  return Array.from(eventBody.matchAll(TUPLET_PART_PATTERN), (match) => {
    const part = match[0]
    const startColumn = tokenStartColumn + 1 + ratioLength + (match.index ?? 0)
    return { token: part, startColumn, endColumn: startColumn + part.length }
  })
}

export function isMetadataLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('//')) return true
  if (trimmed.startsWith('L:') || trimmed.startsWith('@text ')) return true
  if (/^(title|tempo)\s*=/.test(trimmed)) return true
  if (/^1\s*=/.test(trimmed)) return true
  if (/^(key|time)\s*=/i.test(trimmed)) return true
  return /^\d+\/\d+$/.test(trimmed)
}

export function stripInlineComment(line: string): string {
  const commentStart = line.indexOf('//')
  if (commentStart < 0) return line
  return line.slice(0, commentStart)
}

export function isPlayableToken(token: string): boolean {
  if (
    token === '|' ||
    token === '||' ||
    token === '|:' ||
    token === ':|' ||
    /^\*\d+$/.test(token) ||
    /^\d+[.:：]$/.test(token) ||
    /^\d+\/\d+$/.test(token) ||
    token.startsWith('\\') ||
    token.startsWith('^')
  ) {
    return false
  }

  const work = stripEventDecorations(token)
  if (!work || work === '0' || work === '-') return false
  if (work.startsWith('[') && work.endsWith(']')) {
    return work
      .slice(1, -1)
      .split('+')
      .some((part) => PITCH_PATTERN.test(part.trim()))
  }
  return PITCH_PATTERN.test(work)
}

function stripEventDecorations(token: string): string {
  let work = token.trim()
  while (work.startsWith('(')) work = work.slice(1)
  while (work.endsWith(')')) work = work.slice(0, -1)
  if (work.startsWith('~')) work = work.slice(1)
  if (work.endsWith('~')) work = work.slice(0, -1)
  const durationPrefix = work.match(DURATION_PREFIX_PATTERN)?.[0]
  if (durationPrefix && !MICROTONAL_PREFIX_PATTERN.test(work)) {
    work = work.slice(durationPrefix.length)
  }
  while (work.endsWith('-')) work = work.slice(0, -1)
  if (work.endsWith('.')) work = work.slice(0, -1)
  return work
}

export function findNotePageIndex(text: string, noteIndex: number): number | null {
  if (!text || noteIndex < 0) return null

  const spans = findJianpuNoteSpans(text)
  const span = spans.find((s) => s.index === noteIndex)
  if (!span) return null

  const sections = parseJianpuPageSections(text)
  if (sections.length <= 1) return 0

  for (const section of sections) {
    const markerLineIndex = section.markerLineIndex
    const nextSection = sections.find((s) => s.pageIndex === section.pageIndex + 1)
    const nextMarkerLineIndex = nextSection?.markerLineIndex ?? Number.MAX_SAFE_INTEGER

    if (span.line >= markerLineIndex && span.line < nextMarkerLineIndex) {
      return section.pageIndex
    }
  }

  return sections[sections.length - 1]?.pageIndex ?? 0
}
