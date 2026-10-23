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
  | 'ending'
  | 'dynamic'
  | 'ornament'
  | 'lyrics'

export interface JianpuSyntaxToken {
  text: string
  type: JianpuSyntaxTokenType
}

// `/` 是歌词正文保留符号，`/L:` 之后第一个独立 `/`（非 `//` 注释标记）即结束符；
// 歌词块可跨行，与后端 _extract_lyric_blocks 的结束符规则保持一致。
export function findLyricBlockRange(text: string): { start: number; end: number } {
  const start = text.indexOf('/L:')
  if (start < 0) return { start: -1, end: -1 }
  for (let index = start + 3; index < text.length; index += 1) {
    if (text[index] !== '/') continue
    if (text[index - 1] === '/' || text[index + 1] === '/') continue
    return { start, end: index }
  }
  return { start, end: -1 }
}

export function lyricBlockLineIndexes(text: string): Set<number> {
  const { start, end } = findLyricBlockRange(text)
  if (start < 0) return new Set()
  const limit = end < start ? text.length : end + 1
  const before = text.slice(0, start)
  const block = text.slice(start, limit)
  const firstLine = before.split('\n').length - 1
  const result = new Set<number>()
  for (let i = 0; i < block.split('\n').length; i += 1) result.add(firstLine + i)
  return result
}

export function maskJianpuLyricBlocks(text: string): string {
  const { start, end } = findLyricBlockRange(text)
  if (start < 0) return text
  const limit = end < start ? text.length : end + 1
  return text.slice(0, start)
    + text.slice(start, limit).replace(/[^\r\n]/g, ' ')
    + text.slice(limit)
}

const TOKEN_PATTERN = /(\s+|\{[^}]*\}|\$[^$]*\$|\|\||\|:|:\||\||&|[^\s|&]+)/g
const DURATION_PREFIX_PATTERN = /^(?:[whqs]|d+)/
const MICROTONAL_PREFIX_PATTERN = /^(?:qs|qf)/
const PITCH_PATTERN = /^(?:(?:tqf|tqs|qf|qs|bb|x|n|♮|#|b)?[1-7][',]*|[1-7][',]*[#b])$/
// 跳房子：{1.} {2.}（也接受 {1,2.}、全角逗号）开房子，{.} 显式闭房子
const ENDING_PATTERN = /^\{(?:[1-9]\d*(?:\s*[,，]\s*[1-9]\d*)*\.?|\.)\}$/

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

  if (/^\/L:/.test(trimmedStart)) {
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
  if (/^tempo\s*=\s*[^\s|]+$/.test(token)) return 'metadata'
  if (token === '|' || token === '||' || token === '|:' || token === ':|') return 'barline'
  // 声线分隔符（复调小节内 & 分隔多条并行旋律线），按分隔符样式高亮
  if (token === '&') return 'barline'
  if (/^\*\d+$/.test(token)) return 'repeat'
  // 跳房子记号必须在 stripEventDecorations 之前判断（它会剥掉尾部的点）
  if (ENDING_PATTERN.test(token)) return 'ending'
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
  if (/^title\s*=/.test(trimmed)) return true
  if (/^tempo\s*=\s*[^\s|]+$/.test(trimmed)) return true
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
