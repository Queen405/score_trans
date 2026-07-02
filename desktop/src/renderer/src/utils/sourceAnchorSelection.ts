export interface SelectableSourceAnchor {
  start_utf16: number
  end_utf16: number
  valid?: boolean
}

export interface SourceAnchorRange {
  start: number
  end: number
}

const PART_MARKER_PATTERN = /^\s*\/\/\s*@part\s+\d+\s+name="(?:\\.|[^"\\])*"\s*$/gm

export function sourceAnchorRange(
  anchors: SelectableSourceAnchor[],
  partText = '',
): SourceAnchorRange | null {
  const valid = anchors
    .filter((anchor) => anchor.valid !== false)
    .sort((left, right) => left.start_utf16 - right.start_utf16)
  if (!valid.length) return null

  const groups = groupAnchorsByPart(valid, partText)
  const selected = groups.reduce((best, group) => (
    group.length > best.length ? group : best
  ), groups[0]!)

  return {
    start: Math.min(...selected.map((anchor) => anchor.start_utf16)),
    end: Math.max(...selected.map((anchor) => anchor.end_utf16)),
  }
}

function groupAnchorsByPart(
  anchors: SelectableSourceAnchor[],
  text: string,
): SelectableSourceAnchor[][] {
  const starts = partBodyStarts(text)
  if (!starts.length) return [anchors]

  const groups = new Map<number, SelectableSourceAnchor[]>()
  for (const anchor of anchors) {
    const partStart = starts.findLast((start) => start <= anchor.start_utf16) ?? -1
    const group = groups.get(partStart) ?? []
    group.push(anchor)
    groups.set(partStart, group)
  }
  return [...groups.values()]
}

function partBodyStarts(text: string): number[] {
  const starts: number[] = []
  PART_MARKER_PATTERN.lastIndex = 0
  for (const match of text.matchAll(PART_MARKER_PATTERN)) {
    let start = (match.index ?? 0) + match[0].length
    if (text.slice(start, start + 2) === '\r\n') start += 2
    else if (text[start] === '\n' || text[start] === '\r') start += 1
    starts.push(start)
  }
  return starts
}
