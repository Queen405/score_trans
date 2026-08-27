import {
  TOKEN_PATTERN,
  TUPLET_RATIO_PATTERN,
  isMetadataLine,
  stripInlineComment,
  isPlayableToken,
} from './jianpuPlayback'

const PITCH_OCTAVE_PATTERN = /([1-7])([',]*)/g

// 检测调号变化：找出文本中所有 1=X 标记
export function detectKeyChanges(text: string): Array<{ lineIndex: number; key: string }> {
  const lines = text.split('\n')
  const changes: Array<{ lineIndex: number; key: string }> = []
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    // 匹配 1=G, 1=C# 等
    if (/^1\s*=[A-Gb#]$/.test(line)) {
      const match = line.match(/^1\s*=(.+)/)
      if (match) {
        changes.push({ lineIndex: i, key: match[1].trim() })
      }
    }
  }
  
  return changes
}

// 比较新旧文本的调号变化，返回发生变化的行索引和新的调号
export function findKeyChangePoints(oldText: string, newText: string): Array<{ lineIndex: number; newKey: string }> {
  const oldKeys = detectKeyChanges(oldText)
  const newKeys = detectKeyChanges(newText)
  
  // 构建旧调号的 lineIndex -> key 映射
  const oldKeyMap = new Map(oldKeys.map(({ lineIndex, key }) => [lineIndex, key]))
  
  // 查找新文本中有变化或新增的调号
  const result: Array<{ lineIndex: number; newKey: string }> = []
  
  for (const { lineIndex, key } of newKeys) {
    const oldKey = oldKeyMap.get(lineIndex)
    if (oldKey !== key) {
      result.push({ lineIndex, newKey: key })
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
