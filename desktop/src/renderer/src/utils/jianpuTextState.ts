const SHA256 = 'SHA-256'
const MAX_EDIT_DISTANCE = 2048

type DiffKind = 'equal' | 'insert' | 'delete'

interface DiffOperation {
  kind: DiffKind
  value: string
}

interface TextEdit {
  start: number
  end: number
  replacement: string[]
}

export async function hashJianpuText(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text)
  const digest = await globalThis.crypto.subtle.digest(SHA256, bytes)
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')
}

export async function hasJianpuTextEdits(
  currentText: string,
  canonicalText: string,
  canonicalHash: string,
  dirty = false,
): Promise<boolean> {
  if (dirty || currentText !== canonicalText) return true
  if (!canonicalHash) return false
  if (!globalThis.crypto?.subtle) return false
  return (await hashJianpuText(currentText)) !== canonicalHash
}

export function preserveEditedJianpuText(
  currentText: string,
  generatedText: string,
  hasEdits: boolean,
  previousGeneratedText?: string,
): string {
  if (!hasEdits) return generatedText
  if (previousGeneratedText === undefined) return currentText
  return mergeGeneratedCorrection(previousGeneratedText, currentText, generatedText)
}

function mergeGeneratedCorrection(
  previousGeneratedText: string,
  currentText: string,
  generatedText: string,
): string {
  const base = Array.from(previousGeneratedText)
  const userEdits = textEdits(base, Array.from(currentText))
  const correctionEdits = textEdits(base, Array.from(generatedText))
  const retainedUserEdits = userEdits.filter(
    (edit) => !correctionEdits.some((correction) => editsConflict(edit, correction)),
  )
  const edits = [...correctionEdits, ...retainedUserEdits].sort((left, right) => (
    left.start - right.start || left.end - right.end
  ))

  const result: string[] = []
  let cursor = 0
  for (const edit of edits) {
    if (edit.start < cursor) continue
    result.push(...base.slice(cursor, edit.start), ...edit.replacement)
    cursor = edit.end
  }
  result.push(...base.slice(cursor))
  return result.join('')
}

function textEdits(base: string[], target: string[]): TextEdit[] {
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
  const operations = shortestEditScript(baseMiddle, targetMiddle)
  if (!operations) {
    return [{
      start: prefix,
      end: base.length - suffix,
      replacement: targetMiddle,
    }]
  }
  return operationsToEdits(operations, prefix)
}

function shortestEditScript(source: string[], target: string[]): DiffOperation[] | null {
  const maximum = source.length + target.length
  const limit = Math.min(maximum, MAX_EDIT_DISTANCE)
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

function backtrackDiff(
  trace: Map<number, number>[],
  source: string[],
  target: string[],
): DiffOperation[] {
  const reversed: DiffOperation[] = []
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

function operationsToEdits(operations: DiffOperation[], baseOffset: number): TextEdit[] {
  const edits: TextEdit[] = []
  let baseIndex = baseOffset
  let pending: TextEdit | null = null

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

function editsConflict(left: TextEdit, right: TextEdit): boolean {
  const leftInsertion = left.start === left.end
  const rightInsertion = right.start === right.end
  if (leftInsertion && rightInsertion) return left.start === right.start
  if (leftInsertion) return left.start > right.start && left.start < right.end
  if (rightInsertion) return right.start > left.start && right.start < left.end
  return left.start < right.end && right.start < left.end
}
