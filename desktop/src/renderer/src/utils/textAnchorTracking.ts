import type { TextAnchor } from '../models/types'
import { sequenceEdits } from './textDiff'

export interface AnchorUpdate {
  anchors: TextAnchor[]
  invalidatedSourceIds: string[]
}

export interface AnchorReconciliation extends AnchorUpdate {
  reconciled: boolean
}

export function reconcileTextAnchors(
  baselineText: string,
  currentText: string,
  baselineAnchors: TextAnchor[],
  previousAnchors: TextAnchor[] = baselineAnchors,
): AnchorReconciliation {
  if (baselineText === currentText) {
    return {
      anchors: baselineAnchors.map(copyAnchor),
      invalidatedSourceIds: [],
      reconciled: true,
    }
  }

  const edits = sequenceEdits(baselineText.split(''), currentText.split(''))
  if (!edits) {
    const anchors = previousAnchors.map(copyAnchor)
    return {
      anchors,
      invalidatedSourceIds: invalidSourceIds(anchors),
      reconciled: false,
    }
  }

  let workingText = baselineText
  let anchors = baselineAnchors.map(copyAnchor)
  for (const edit of [...edits].sort((left, right) => right.start - left.start)) {
    const nextText = workingText.slice(0, edit.start)
      + edit.replacement.join('')
      + workingText.slice(edit.end)
    anchors = trackTextAnchors(workingText, nextText, anchors).anchors
    workingText = nextText
  }
  return {
    anchors,
    invalidatedSourceIds: invalidSourceIds(anchors),
    reconciled: true,
  }
}

/**
 * Track one textarea input operation. JavaScript string offsets are UTF-16 offsets, matching the
 * backend contract and HTMLTextAreaElement selection APIs.
 */
export function trackTextAnchors(
  previous: string,
  current: string,
  anchors: TextAnchor[],
): AnchorUpdate {
  if (previous === current) return { anchors: anchors.map(copyAnchor), invalidatedSourceIds: [] }

  const prefix = commonPrefixLength(previous, current)
  const suffix = commonSuffixLength(previous, current, prefix)
  const oldEnd = previous.length - suffix
  const newEnd = current.length - suffix
  const delta = (newEnd - prefix) - (oldEnd - prefix)
  const affected = anchors.filter((anchor) => (
    anchor.valid !== false && overlapsEdit(anchor, prefix, oldEnd)
  ))
  const replacement = current.slice(prefix, newEnd)
  const canRetainSingle = affected.length === 1
    && prefix >= affected[0]!.start_utf16
    && oldEnd <= affected[0]!.end_utf16
    && affected[0]!.end_utf16 - affected[0]!.start_utf16 + delta > 0
    && replacement.length > 0
    && !/\s/.test(replacement)
    && !['|', '[', ']', '+'].some((separator) => replacement.includes(separator))

  const invalidatedSourceIds: string[] = []
  const next = anchors.map((anchor) => {
    const copy = copyAnchor(anchor)
    if (copy.valid === false) return copy
    if (oldEnd <= copy.start_utf16) {
      copy.start_utf16 += delta
      copy.end_utf16 += delta
      return copy
    }
    if (prefix >= copy.end_utf16) return copy
    if (canRetainSingle && copy.source_id === affected[0]!.source_id
      && copy.start_utf16 === affected[0]!.start_utf16
      && copy.end_utf16 === affected[0]!.end_utf16) {
      copy.end_utf16 = Math.max(copy.start_utf16, copy.end_utf16 + delta)
      return copy
    }
    copy.valid = false
    invalidatedSourceIds.push(copy.source_id)
    return copy
  })

  return { anchors: next, invalidatedSourceIds: [...new Set(invalidatedSourceIds)] }
}

function overlapsEdit(anchor: TextAnchor, start: number, oldEnd: number): boolean {
  if (start === oldEnd) {
    return start > anchor.start_utf16 && start < anchor.end_utf16
  }
  return start < anchor.end_utf16 && oldEnd > anchor.start_utf16
}

function commonPrefixLength(left: string, right: string): number {
  const limit = Math.min(left.length, right.length)
  let index = 0
  while (index < limit && left[index] === right[index]) index += 1
  return index
}

function commonSuffixLength(left: string, right: string, prefix: number): number {
  const limit = Math.min(left.length, right.length) - prefix
  let length = 0
  while (
    length < limit
    && left[left.length - 1 - length] === right[right.length - 1 - length]
  ) {
    length += 1
  }
  return length
}

function copyAnchor(anchor: TextAnchor): TextAnchor {
  return { ...anchor }
}

function invalidSourceIds(anchors: TextAnchor[]): string[] {
  return [...new Set(
    anchors.filter((anchor) => anchor.valid === false).map((anchor) => anchor.source_id),
  )]
}
