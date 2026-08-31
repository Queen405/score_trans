import type { RekeyAnchorMapping, TextAnchor } from '../models/types'
import { sequenceEdits } from './textDiff'

export interface AnchorUpdate {
  anchors: TextAnchor[]
  invalidatedSourceIds: string[]
}

export interface AnchorReconciliation extends AnchorUpdate {
  reconciled: boolean
}

export type RekeySpanMapping = RekeyAnchorMapping

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
 * Apply the backend's semantic rekey mapping to existing source anchors.
 *
 * The mapping coordinates use the rekey request text (the new key with old
 * pitches) and the response text. Role spans handle anchors inside a changed
 * pitch; all other anchors are shifted by the changed pitch spans.
 */
export function reconcileRekeyedTextAnchors(
  anchors: TextAnchor[],
  mappings: readonly RekeySpanMapping[],
): AnchorReconciliation {
  const sorted = [...mappings].sort((left, right) => (
    left.old_start_utf16 - right.old_start_utf16
    || left.old_end_utf16 - right.old_end_utf16
  ))
  const pitchMappings = sorted.filter((mapping) => mapping.role === 'pitch')
  const next = anchors.map((anchor) => {
    const copy = copyAnchor(anchor)
    if (copy.valid === false) return copy

    const direct = sorted
      .filter((mapping) => mapping.role === copy.role && contains(mapping, copy))
      .sort((left, right) => (
        (left.old_end_utf16 - left.old_start_utf16)
        - (right.old_end_utf16 - right.old_start_utf16)
      ))[0]
    if (direct) {
      copy.start_utf16 = direct.new_start_utf16
      copy.end_utf16 = direct.new_end_utf16
      return copy
    }

    if (pitchMappings.some((mapping) => overlaps(mapping, copy))) {
      copy.valid = false
      return copy
    }
    copy.start_utf16 = mapOffset(copy.start_utf16, pitchMappings)
    copy.end_utf16 = mapOffset(copy.end_utf16, pitchMappings)
    return copy
  })
  return {
    anchors: next,
    invalidatedSourceIds: invalidSourceIds(next),
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

function contains(mapping: RekeySpanMapping, anchor: TextAnchor): boolean {
  return mapping.old_start_utf16 <= anchor.start_utf16
    && mapping.old_end_utf16 >= anchor.end_utf16
}

function overlaps(mapping: RekeySpanMapping, anchor: TextAnchor): boolean {
  return mapping.old_start_utf16 < anchor.end_utf16
    && mapping.old_end_utf16 > anchor.start_utf16
}

function mapOffset(offset: number, mappings: readonly RekeySpanMapping[]): number {
  let delta = 0
  for (const mapping of mappings) {
    if (offset < mapping.old_start_utf16) break
    if (offset >= mapping.old_end_utf16) {
      delta += (mapping.new_end_utf16 - mapping.new_start_utf16)
        - (mapping.old_end_utf16 - mapping.old_start_utf16)
      continue
    }
    const relative = offset - mapping.old_start_utf16
    const newLength = mapping.new_end_utf16 - mapping.new_start_utf16
    return mapping.new_start_utf16 + Math.min(relative, newLength)
  }
  return offset + delta
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
