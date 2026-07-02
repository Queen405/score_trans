import { parseJianpuPageSections } from './jianpuPageSections'

export interface JianpuNoteSpan {
  index: number
  line: number
  startColumn: number
  endColumn: number
  token: string
}

const TOKEN_PATTERN = /\$[^$]+\$|\|\||\|:|:\||\||[^\s|]+/g
const DURATION_PREFIX_PATTERN = /^[whqsd]/
const PITCH_PATTERN = /^(?:(?:bb|x|n|♮|#|b)?[1-7][',]*|[1-7][',]*[#b])$/
const TUPLET_PART_PATTERN = /(?:bb|x|n|♮|#|b)?[0-7][',]*[#b]?/g

export function findJianpuNoteSpans(text: string): JianpuNoteSpan[] {
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

function isTupletToken(token: string): boolean {
  return token.startsWith('$') && token.endsWith('$') && token.length > 2
}

function tupletPartSpans(
  token: string,
  tokenStartColumn: number,
): Array<{ token: string; startColumn: number; endColumn: number }> {
  const body = token.slice(1, -1)
  if (/\s/.test(body)) {
    return Array.from(body.matchAll(/\S+/g), (match) => {
      const part = match[0]
      const startColumn = tokenStartColumn + 1 + (match.index ?? 0)
      return { token: part, startColumn, endColumn: startColumn + part.length }
    })
  }
  return Array.from(body.matchAll(TUPLET_PART_PATTERN), (match) => {
    const part = match[0]
    const startColumn = tokenStartColumn + 1 + (match.index ?? 0)
    return { token: part, startColumn, endColumn: startColumn + part.length }
  })
}

function isMetadataLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('//')) return true
  if (trimmed.startsWith('L:') || trimmed.startsWith('@text ')) return true
  if (/^(title|tempo)\s*=/.test(trimmed)) return true
  if (/^1\s*=/.test(trimmed)) return true
  if (/^(key|time)\s*=/i.test(trimmed)) return true
  return /^\d+\/\d+$/.test(trimmed)
}

function stripInlineComment(line: string): string {
  const commentStart = line.indexOf('//')
  if (commentStart < 0) return line
  return line.slice(0, commentStart)
}

function isPlayableToken(token: string): boolean {
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
  if (DURATION_PREFIX_PATTERN.test(work)) work = work.slice(1)
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
