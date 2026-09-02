export type JianpuSyntaxTokenType =
  | 'plain'
  | 'comment'
  | 'metadata'
  | 'note'
  | 'rest'
  | 'chord'
  | 'tuplet'
  | 'barline'
  | 'repeat'
  | 'dynamic'
  | 'ornament'
  | 'lyrics'

export interface JianpuSyntaxToken {
  text: string
  type: JianpuSyntaxTokenType
}

const TOKEN_PATTERN = /(\s+|\$[^$]*\$|\|\||\|:|:\||\||[^\s|]+)/g
const DURATION_PREFIX_PATTERN = /^(?:[whqs]|d+)/
const MICROTONAL_PREFIX_PATTERN = /^(?:qs|qf)/
const PITCH_PATTERN = /^(?:(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[1-7][',]*|[1-7][',]*[#b])$/

export function tokenizeJianpuLine(line: string): JianpuSyntaxToken[] {
  if (!line) return []

  const commentStart = line.indexOf('//')
  const code = commentStart >= 0 ? line.slice(0, commentStart) : line
  const comment = commentStart >= 0 ? line.slice(commentStart) : ''

  const codeTokens = tokenizeCodePart(code)
  if (comment) {
    codeTokens.push({ text: comment, type: 'comment' })
  }
  return codeTokens
}

function tokenizeCodePart(code: string): JianpuSyntaxToken[] {
  if (!code) return []

  const leadingWhitespace = code.match(/^\s*/)?.[0] ?? ''
  const trimmedStart = code.slice(leadingWhitespace.length)
  const trimmed = code.trim()

  if (!trimmed) {
    return [{ text: code, type: 'plain' }]
  }

  if (trimmedStart.startsWith('L:')) {
    return [
      ...(leadingWhitespace ? [{ text: leadingWhitespace, type: 'plain' as const }] : []),
      { text: trimmedStart, type: 'lyrics' },
    ]
  }

  if (isMetadataLine(trimmed)) {
    return [
      ...(leadingWhitespace ? [{ text: leadingWhitespace, type: 'plain' as const }] : []),
      { text: trimmedStart, type: 'metadata' },
    ]
  }

  return Array.from(code.matchAll(TOKEN_PATTERN), (match) => {
    const text = match[0]
    return { text, type: classifyToken(text) }
  })
}

function classifyToken(token: string): JianpuSyntaxTokenType {
  if (!token.trim()) return 'plain'
  if (token === '|' || token === '||' || token === '|:' || token === ':|') return 'barline'
  if (/^\*\d+$/.test(token)) return 'repeat'
  if (token.startsWith('\\')) return 'dynamic'
  if (token.startsWith('^') || token.startsWith('(^')) return 'ornament'
  if (token.startsWith('$') && token.endsWith('$') && token.length > 2) return 'tuplet'
  if (token === '0' || token === '-') return 'rest'

  const work = stripEventDecorations(token)
  if (isChordToken(work)) return 'chord'
  if (work === '0' || work === '-') return 'rest'
  if (PITCH_PATTERN.test(work)) return 'note'
  return 'plain'
}

function isMetadataLine(trimmed: string): boolean {
  if (/^(title|tempo)\s*=/.test(trimmed)) return true
  if (/^1\s*=/.test(trimmed)) return true
  if (/^(key|time)\s*=/i.test(trimmed)) return true
  return /^\d+\/\d+$/.test(trimmed)
}

function isChordToken(token: string): boolean {
  if (!token.startsWith('[') || !token.endsWith(']')) return false
  return token
    .slice(1, -1)
    .split('+')
    .some((part) => PITCH_PATTERN.test(stripEventDecorations(part.trim())))
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
  while (work.endsWith('.')) work = work.slice(0, -1)
  return work
}
