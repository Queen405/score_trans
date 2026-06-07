export interface JianpuNoteSpan {
  index: number
  line: number
  startColumn: number
  endColumn: number
  token: string
}

const TOKEN_PATTERN = /\|\||\|:|:\||\||[^\s|]+/g
const DURATION_PREFIX_PATTERN = /^[whqsd]/
const PITCH_PATTERN = /^(?:(?:bb|x|n|♮|#|b)?[1-7][',]*|[1-7][',]*[#b])$/

export function findJianpuNoteSpans(text: string): JianpuNoteSpan[] {
  const spans: JianpuNoteSpan[] = []
  let noteIndex = 0

  text.split('\n').forEach((line, lineIndex) => {
    if (isMetadataLine(line)) return

    for (const match of line.matchAll(TOKEN_PATTERN)) {
      const token = match[0]
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

function isMetadataLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#')) return true
  if (trimmed.startsWith('L:') || trimmed.startsWith('@text ')) return true
  if (/^(title|tempo)\s*=/.test(trimmed)) return true
  if (/^1\s*=/.test(trimmed)) return true
  if (/^(key|time)\s*=/i.test(trimmed)) return true
  return /^\d+\/\d+$/.test(trimmed)
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
