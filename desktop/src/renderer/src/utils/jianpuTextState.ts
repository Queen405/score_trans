import { sequenceEdits, type SequenceEdit } from './textDiff'

const SHA256 = 'SHA-256'
type TextEdit = SequenceEdit<string>

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
  const edits = sequenceEdits(base, target)
  if (edits) return edits

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
  return [{
    start: prefix,
    end: base.length - suffix,
    replacement: target.slice(prefix, target.length - suffix),
  }]
}

function editsConflict(left: TextEdit, right: TextEdit): boolean {
  const leftInsertion = left.start === left.end
  const rightInsertion = right.start === right.end
  if (leftInsertion && rightInsertion) return left.start === right.start
  if (leftInsertion) return left.start > right.start && left.start < right.end
  if (rightInsertion) return right.start > left.start && right.start < left.end
  return left.start < right.end && right.start < left.end
}
