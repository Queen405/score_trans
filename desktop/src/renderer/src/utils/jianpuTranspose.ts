import {
  TOKEN_PATTERN,
  TUPLET_RATIO_PATTERN,
  isMetadataLine,
  stripInlineComment,
  isPlayableToken,
} from './jianpuPlayback'

const PITCH_OCTAVE_PATTERN = /([1-7])([',]*)/g

// 调号 token:1=X(X=[A-G][#b]*)，须是独立 token(前后为行首/空白/小节线)，
// 因此能识别独占一行的 1=G、紧跟 | 之后的 1=G，以及多字符调号 1=Bb/1=F#。
const KEY_TOKEN_PATTERN = /1\s*=\s*([A-G][#b]*)/g

// 检测文本中所有调号 token 的(行号, 调号)
export function detectKeyChanges(text: string): Array<{ lineIndex: number; key: string }> {
  const changes: Array<{ lineIndex: number; key: string }> = []
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    for (const match of line.matchAll(KEY_TOKEN_PATTERN)) {
      const start = match.index ?? 0
      const end = start + match[0].length
      const prevOk = start === 0 || /[\s|]/.test(line[start - 1])
      const nextOk = end === line.length || /[\s|]/.test(line[end])
      if (prevOk && nextOk) changes.push({ lineIndex: i, key: match[1] })
    }
  }
  return changes
}

// 比较新旧文本的调号 token 序列，返回发生变化的(行号, 新调号)
export function findKeyChangePoints(oldText: string, newText: string): Array<{ lineIndex: number; newKey: string }> {
  const oldKeys = detectKeyChanges(oldText)
  const newKeys = detectKeyChanges(newText)
  const result: Array<{ lineIndex: number; newKey: string }> = []
  const count = Math.max(oldKeys.length, newKeys.length)
  for (let i = 0; i < count; i++) {
    const oldKey = oldKeys[i]?.key
    const newKey = newKeys[i]?.key
    if (newKey !== undefined && oldKey !== newKey) {
      result.push({ lineIndex: newKeys[i].lineIndex, newKey })
    }
  }
  return result
}

function shiftOctaveChars(octaveChars: string, direction: number): string {
  const up = (octaveChars.match(/'/g) || []).length
  const down = (octaveChars.match(/,/g) || []).length
  const net = up - down + direction
  return "'".repeat(Math.max(0, net)) + ','.repeat(Math.max(0, -net))
}

function replacePitches(s: string, direction: number): string {
  return s.replace(PITCH_OCTAVE_PATTERN, (_match, digit: string, octaveChars: string) => {
    return `${digit}${shiftOctaveChars(octaveChars, direction)}`
  })
}

function transformToken(token: string, direction: number): string {
  if (token.startsWith('$') && token.endsWith('$') && token.length > 2) {
    const body = token.slice(1, -1)
    const ratioMatch = body.match(TUPLET_RATIO_PATTERN)
    const ratioLen = ratioMatch ? ratioMatch[0].length : 0
    const ratio = body.slice(0, ratioLen)
    const eventBody = body.slice(ratioLen)
    return `$${ratio}${replacePitches(eventBody, direction)}$`
  }
  if (!isPlayableToken(token)) return token
  return replacePitches(token, direction)
}

export function transposeOctave(text: string, direction: 1 | -1): string {
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  return lines
    .map((line) => {
      const code = stripInlineComment(line)
      if (isMetadataLine(code)) return line
      const comment = line.slice(code.length)
      const transformed = code.replace(TOKEN_PATTERN, (match) => transformToken(match, direction))
      return transformed + comment
    })
    .join('\n')
}
