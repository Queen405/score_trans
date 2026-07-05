import {
  TOKEN_PATTERN,
  TUPLET_RATIO_PATTERN,
  isMetadataLine,
  stripInlineComment,
  isPlayableToken,
} from './jianpuPlayback'

const PITCH_OCTAVE_PATTERN = /([1-7])([',]*)/g

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
