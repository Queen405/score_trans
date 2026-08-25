export const MAX_EDIT_DISTANCE = 2048

type DiffKind = 'equal' | 'insert' | 'delete'

interface DiffOperation<T> {
  kind: DiffKind
  value: T
}

export interface SequenceEdit<T> {
  start: number
  end: number
  replacement: T[]
}

export function sequenceEdits<T>(
  base: readonly T[],
  target: readonly T[],
  maxEditDistance = MAX_EDIT_DISTANCE,
): SequenceEdit<T>[] | null {
  let prefix = 0
  while (prefix < base.length && prefix < target.length && base[prefix] === target[prefix]) {
    prefix += 1
  }
  let suffix = 0
  while (
    suffix < base.length - prefix
    && suffix < target.length - prefix
    && base[base.length - 1 - suffix] === target[target.length - 1 - suffix]
  ) {
    suffix += 1
  }

  const baseMiddle = base.slice(prefix, base.length - suffix)
  const targetMiddle = target.slice(prefix, target.length - suffix)
  if (!baseMiddle.length && !targetMiddle.length) return []
  if (!baseMiddle.length) {
    return [{ start: prefix, end: prefix, replacement: [...targetMiddle] }]
  }
  if (!targetMiddle.length) {
    return [{ start: prefix, end: base.length - suffix, replacement: [] }]
  }

  const operations = shortestEditScript(baseMiddle, targetMiddle, maxEditDistance)
  return operations ? operationsToEdits(operations, prefix) : null
}

function shortestEditScript<T>(
  source: readonly T[],
  target: readonly T[],
  maxEditDistance: number,
): DiffOperation<T>[] | null {
  const maximum = source.length + target.length
  const limit = Math.min(maximum, maxEditDistance)
  const frontier = new Map<number, number>([[1, 0]])
  const trace: Map<number, number>[] = []

  for (let distance = 0; distance <= limit; distance += 1) {
    trace.push(new Map(frontier))
    for (let diagonal = -distance; diagonal <= distance; diagonal += 2) {
      const left = frontier.get(diagonal - 1) ?? Number.NEGATIVE_INFINITY
      const down = frontier.get(diagonal + 1) ?? Number.NEGATIVE_INFINITY
      let x = diagonal === -distance || (diagonal !== distance && left < down)
        ? down
        : left + 1
      if (!Number.isFinite(x)) x = 0
      let y = x - diagonal
      while (x < source.length && y < target.length && source[x] === target[y]) {
        x += 1
        y += 1
      }
      frontier.set(diagonal, x)
      if (x === source.length && y === target.length) {
        return backtrackDiff(trace, source, target)
      }
    }
  }
  return null
}

function backtrackDiff<T>(
  trace: Map<number, number>[],
  source: readonly T[],
  target: readonly T[],
): DiffOperation<T>[] {
  const reversed: DiffOperation<T>[] = []
  let x = source.length
  let y = target.length

  for (let distance = trace.length - 1; distance >= 0; distance -= 1) {
    const frontier = trace[distance]!
    const diagonal = x - y
    const left = frontier.get(diagonal - 1) ?? Number.NEGATIVE_INFINITY
    const down = frontier.get(diagonal + 1) ?? Number.NEGATIVE_INFINITY
    const previousDiagonal = diagonal === -distance
      || (diagonal !== distance && left < down)
      ? diagonal + 1
      : diagonal - 1
    const previousX = frontier.get(previousDiagonal) ?? 0
    const previousY = previousX - previousDiagonal

    while (x > previousX && y > previousY) {
      reversed.push({ kind: 'equal', value: source[x - 1]! })
      x -= 1
      y -= 1
    }
    if (distance === 0) break
    if (x === previousX) {
      reversed.push({ kind: 'insert', value: target[y - 1]! })
      y -= 1
    } else {
      reversed.push({ kind: 'delete', value: source[x - 1]! })
      x -= 1
    }
  }
  return reversed.reverse()
}

function operationsToEdits<T>(
  operations: DiffOperation<T>[],
  baseOffset: number,
): SequenceEdit<T>[] {
  const edits: SequenceEdit<T>[] = []
  let baseIndex = baseOffset
  let pending: SequenceEdit<T> | null = null

  const flush = (): void => {
    if (!pending) return
    edits.push(pending)
    pending = null
  }
  for (const operation of operations) {
    if (operation.kind === 'equal') {
      flush()
      baseIndex += 1
      continue
    }
    pending ??= { start: baseIndex, end: baseIndex, replacement: [] }
    if (operation.kind === 'delete') {
      baseIndex += 1
      pending.end = baseIndex
    } else {
      pending.replacement.push(operation.value)
    }
  }
  flush()
  return edits
}
