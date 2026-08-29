import {
  TOKEN_PATTERN,
  TUPLET_RATIO_PATTERN,
  isMetadataLine,
  stripInlineComment,
  isPlayableToken,
} from './jianpuPlayback'

const PITCH_OCTAVE_PATTERN = /([1-7])([',]*)/g

// 调号 token:1=X(X=[A-G] 后跟至多一个 # 或 b)，须是独立 token(前后为行首/空白/
// 小节线)，因此能识别独占一行的 1=G、紧跟 | 之后的 1=G，以及多字符调号 1=Bb/1=F#。
// 词表与后端 domain/rekey.py 的 _KEY_TOKEN 及解析器 _is_key_name 保持一致。
const KEY_HEAD_SOURCE = '1\\s*=\\s*'
const KEY_NAME_SOURCE = '[A-G](?:#|b)?'
const KEY_TOKEN_PATTERN = new RegExp(`${KEY_HEAD_SOURCE}(${KEY_NAME_SOURCE})`, 'g')
// 「打了一半的调号」：1= 后面的调名可以缺失或只写了字母。与上面同源拼装，避免两条
// 正则各自演化后判定互相矛盾。
const KEY_PREFIX_PATTERN = new RegExp(`${KEY_HEAD_SOURCE}[A-G]?`, 'g')

// 检测文本中所有调号 token 的(行号, 调号)。行内注释与歌词行内的 1=X 不算调号，
// 否则「// 1=G」这类文本会白发一次转调请求。
export function detectKeyChanges(text: string): Array<{ lineIndex: number; key: string }> {
  const changes: Array<{ lineIndex: number; key: string }> = []
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = stripInlineComment(lines[i])
    if (!line.trim()) continue
    if (isLyricOrTextLine(line)) continue
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

// 歌词行(L:)与文本行(@text)可能含 1=X 字样，但它们不是调号。
// 不能直接用 isMetadataLine：调号行本身就是 metadata，正是我们要找的目标。
function isLyricOrTextLine(line: string): boolean {
  const trimmed = line.trim()
  return trimmed.startsWith('L:') || trimmed.startsWith('@text ')
}

/**
 * 把 before 中的一个偏移映射到 after 中的对应位置。
 *
 * 转调会重写文档中间的一段，用「整篇长度差」平移光标会在光标位于改动区之前时
 * 把它推到没动过的文本后面。这里按公共前后缀分三种情形处理：
 * 改动区之前不动、改动区之后平移、改动区之内钳到区末。
 */
export function remapOffset(before: string, after: string, offset: number): number {
  if (before === after) return offset
  const clamped = Math.max(0, Math.min(offset, before.length))
  const shorter = Math.min(before.length, after.length)
  let prefix = 0
  while (prefix < shorter && before[prefix] === after[prefix]) prefix += 1
  if (clamped <= prefix) return clamped
  let suffix = 0
  while (
    suffix < shorter - prefix
    && before[before.length - 1 - suffix] === after[after.length - 1 - suffix]
  ) {
    suffix += 1
  }
  if (clamped >= before.length - suffix) return clamped + (after.length - before.length)
  return after.length - suffix
}

export type KeyEditVerdict = 'unchanged' | 'no-key' | 'key-removed' | 'transposable'

/**
 * 一次编辑相对基线的调号判定。
 *
 * - unchanged：调号值序列没变，无需转调。
 * - no-key：新文本里还有打了一半的调号（如 1=、1=E5），调号数却变少了。
 * - key-removed：调号被删干净了，没留残片。后端会把被删调号管辖的音符回退到
 *   此刻真正生效的调，所以这一类必须发请求。
 * - transposable：调号序列变了且新文本仍有完整调号。
 *
 * unchanged 与 no-key 多为打字中间态，调用方应当保留基线，否则最初那个「编辑前的
 * 合法文本」会被中间态换掉，真正的换调就再也找不到旧调。
 *
 * 判定刻意宽松——真正的区间定位与转调由后端负责；多发一次请求只是浪费，
 * 漏发则功能失效。
 */
export function classifyKeyEdit(oldText: string, newText: string): KeyEditVerdict {
  const oldKeys = detectKeyChanges(oldText).map((item) => item.key)
  const newKeys = detectKeyChanges(newText).map((item) => item.key)
  const changed = oldKeys.length !== newKeys.length
    || oldKeys.some((key, index) => key !== newKeys[index])
  if (!changed) return 'unchanged'
  if (newKeys.length >= oldKeys.length) return 'transposable'
  // 调号变少了：可能是删干净，也可能是正打到一半。中间态一定留着 1= 残片，
  // 删除则不留——只有后者能让后端定出回退目标。
  return hasUnfinishedKey(newText) ? 'no-key' : 'key-removed'
}

// 是否存在「1= 已敲下但调名尚未成形」的位置。逐行剔除注释与歌词后，比较完整调号
// 与 1= 前缀的出现次数：前缀多于完整调号即说明有一处还没写完。
function hasUnfinishedKey(text: string): boolean {
  for (const rawLine of text.replace(/\r\n?/g, '\n').split('\n')) {
    const line = stripInlineComment(rawLine)
    if (!line.trim()) continue
    if (isLyricOrTextLine(line)) continue
    const full = Array.from(line.matchAll(KEY_TOKEN_PATTERN)).length
    const prefixes = Array.from(line.matchAll(KEY_PREFIX_PATTERN)).length
    if (prefixes > full) return true
  }
  return false
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
