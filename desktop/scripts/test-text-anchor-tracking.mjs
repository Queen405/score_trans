import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const sourceUrl = new URL(
  '../src/renderer/src/utils/textAnchorTracking.ts',
  import.meta.url,
)
const diffSourceUrl = new URL(
  '../src/renderer/src/utils/textDiff.ts',
  import.meta.url,
)
const diffSource = await readFile(diffSourceUrl, 'utf8')
const diffJavascript = ts.transpileModule(diffSource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText
const diffModuleUrl = `data:text/javascript;base64,${Buffer.from(diffJavascript).toString('base64')}`
const source = (await readFile(sourceUrl, 'utf8')).replace(
  "from './textDiff'",
  `from '${diffModuleUrl}'`,
)
const javascript = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText
const moduleUrl = `data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`
const { reconcileRekeyedTextAnchors, reconcileTextAnchors, trackTextAnchors } = await import(moduleUrl)

const selectionSourceUrl = new URL(
  '../src/renderer/src/utils/sourceAnchorSelection.ts',
  import.meta.url,
)
const selectionSource = await readFile(selectionSourceUrl, 'utf8')
const selectionJavascript = ts.transpileModule(selectionSource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText
const selectionModuleUrl = `data:text/javascript;base64,${Buffer.from(selectionJavascript).toString('base64')}`
const { sourceAnchorRange } = await import(selectionModuleUrl)

const pageSourceUrl = new URL(
  '../src/renderer/src/utils/jianpuPageSections.ts',
  import.meta.url,
)
const pageJavascript = ts.transpileModule(await readFile(pageSourceUrl, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText
const pageUtils = await import(
  `data:text/javascript;base64,${Buffer.from(pageJavascript).toString('base64')}`,
)

const anchor = (source_id, start_utf16, end_utf16) => ({
  source_id,
  start_utf16,
  end_utf16,
  role: 'note',
  valid: true,
})

test('edit before anchors shifts UTF-16 ranges', () => {
  const result = trackTextAnchors('1 2', '标题 1 2', [anchor('s1:i1', 0, 1)])
  assert.deepEqual(result.anchors[0], anchor('s1:i1', 3, 4))
})

test('single-token pitch replacement retains provenance', () => {
  const result = trackTextAnchors('1 3 5', '1 4 5', [anchor('s1:i2', 2, 3)])
  assert.equal(result.anchors[0].valid, true)
  assert.equal(result.anchors[0].start_utf16, 2)
  assert.equal(result.anchors[0].end_utf16, 3)
})

test('rekey mapping retains note and accidental anchors across length changes', () => {
  const before = '1=D\n6 b7, |'
  const after = '1=D\n7 #1 |'
  const noteStart = before.indexOf('6')
  const accidentalStart = before.indexOf('b7')
  const accidentalAfter = after.indexOf('#1')
  const result = reconcileRekeyedTextAnchors(
    [
      anchor('note-1', noteStart, noteStart + 1),
      { ...anchor('acc-1', accidentalStart, accidentalStart + 1), role: 'accidental' },
    ],
    [
      {
        role: 'pitch', old_start_utf16: noteStart, old_end_utf16: noteStart + 1,
        new_start_utf16: after.indexOf('7'), new_end_utf16: after.indexOf('7') + 1,
      },
      {
        role: 'note', old_start_utf16: noteStart, old_end_utf16: noteStart + 1,
        new_start_utf16: after.indexOf('7'), new_end_utf16: after.indexOf('7') + 1,
      },
      {
        role: 'pitch', old_start_utf16: accidentalStart, old_end_utf16: accidentalStart + 2,
        new_start_utf16: accidentalAfter, new_end_utf16: accidentalAfter + 2,
      },
      {
        role: 'accidental', old_start_utf16: accidentalStart, old_end_utf16: accidentalStart + 1,
        new_start_utf16: accidentalAfter, new_end_utf16: accidentalAfter + 1,
      },
      {
        role: 'note', old_start_utf16: accidentalStart + 1, old_end_utf16: accidentalStart + 2,
        new_start_utf16: accidentalAfter + 1, new_end_utf16: accidentalAfter + 2,
      },
    ],
  )

  assert.deepEqual(result.anchors.map((item) => [item.valid, item.start_utf16, item.end_utf16]), [
    [true, after.indexOf('7'), after.indexOf('7') + 1],
    [true, accidentalAfter, accidentalAfter + 1],
  ])
})

test('rekey mapping shifts unchanged anchors after a rewritten pitch', () => {
  const before = '1=D\n1 b7, (1) |'
  const after = '1=D\n1 #1 (1) |'
  const oldPitch = before.indexOf('b7')
  const newPitch = after.indexOf('#1')
  const oldSlur = before.indexOf('(')
  const result = reconcileRekeyedTextAnchors(
    [anchor('slur-1', oldSlur, oldSlur + 1)],
    [{
      role: 'pitch',
      old_start_utf16: oldPitch,
      old_end_utf16: oldPitch + 3,
      new_start_utf16: newPitch,
      new_end_utf16: newPitch + 2,
    }],
  )

  assert.deepEqual(result.anchors[0], {
    ...anchor('slur-1', after.indexOf('('), after.indexOf('(') + 1),
  })
})

test('rekey mapping rebases a second-page anchor through its page body offset', () => {
  const before = pageUtils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '1=G\n7 1 |' },
  ])
  const after = pageUtils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '1=A\n5 6 |' },
  ])
  const beforeSections = pageUtils.parseJianpuPageSections(before)
  const afterSections = pageUtils.parseJianpuPageSections(after)
  const beforeOffset = pageUtils.jianpuPageSectionBodyOffset(before, beforeSections, 1)
  const afterOffset = pageUtils.jianpuPageSectionBodyOffset(after, afterSections, 1)
  const oldNote = beforeOffset + before.slice(beforeOffset).indexOf('7')
  const newNote = afterOffset + after.slice(afterOffset).indexOf('5')
  const result = reconcileRekeyedTextAnchors(
    [anchor('page-2-note', oldNote, oldNote + 1)],
    [{
      role: 'note',
      old_start_utf16: oldNote,
      old_end_utf16: oldNote + 1,
      new_start_utf16: newNote,
      new_end_utf16: newNote + 1,
    }],
  )
  const local = result.anchors[0]
  assert.deepEqual(local, anchor('page-2-note', newNote, newNote + 1))
  assert.equal(after.slice(local.start_utf16, local.end_utf16), '5')
})

test('cross-token replacement invalidates every affected anchor', () => {
  const result = trackTextAnchors(
    '1 3 5',
    '1 6',
    [anchor('s1:i2', 2, 3), anchor('s1:i3', 4, 5)],
  )
  assert.deepEqual(result.anchors.map((item) => item.valid), [false, false])
  assert.deepEqual(result.invalidatedSourceIds, ['s1:i2', 's1:i3'])
})

test('deleting the complete mapped token invalidates its anchor', () => {
  const result = trackTextAnchors('1 3 5', '1  5', [anchor('s1:i2', 2, 3)])
  assert.equal(result.anchors[0].valid, false)
})

test('pasting multiple tokens into one mapped token invalidates its anchor', () => {
  const result = trackTextAnchors('1 3 5', '1 4 6 5', [anchor('s1:i2', 2, 3)])
  assert.equal(result.anchors[0].valid, false)
})

test('baseline reconciliation uses UTF-16 offsets around astral characters', () => {
  const result = reconcileTextAnchors(
    '😀 1 2',
    '😀 标题 1 2',
    [anchor('s1:i1', 3, 4)],
  )

  assert.equal(result.reconciled, true)
  assert.deepEqual(result.anchors[0], anchor('s1:i1', 6, 7))
})

test('restoring baseline text revalidates a previously invalid anchor', () => {
  const baselineAnchors = [anchor('s1:i2', 2, 3)]
  const deleted = reconcileTextAnchors('1 3 5', '1  5', baselineAnchors)
  const restored = reconcileTextAnchors('1 3 5', '1 3 5', baselineAnchors, deleted.anchors)

  assert.equal(deleted.anchors[0].valid, false)
  assert.deepEqual(restored.anchors[0], baselineAnchors[0])
})

test('separate baseline edits preserve anchors between edited ranges', () => {
  const result = reconcileTextAnchors(
    '1 2 3 4 5',
    '1 7 3 8 5',
    [
      anchor('s1:i2', 2, 3),
      anchor('s1:i3', 4, 5),
      anchor('s1:i4', 6, 7),
    ],
  )

  assert.deepEqual(result.anchors.map((item) => item.valid), [true, true, true])
  assert.deepEqual(result.anchors[1], anchor('s1:i3', 4, 5))
})

test('diff distance overflow preserves the previous anchor state', () => {
  const baselineAnchors = [anchor('s1:i1', 0, 1)]
  const previous = [{ ...baselineAnchors[0], valid: false }]
  const result = reconcileTextAnchors(
    'a'.repeat(2100),
    'b'.repeat(2100),
    baselineAnchors,
    previous,
  )

  assert.equal(result.reconciled, false)
  assert.deepEqual(result.anchors, previous)
})

test('shared source elements select their complete range in one part', () => {
  const text = [
    '// @part 1 name="高音"',
    '1=C',
    '4/4',
    '(1 2) |',
    '// @part 2 name="低音"',
    '1=C',
    '4/4',
    '5 |',
  ].join('\n')
  const open = text.indexOf('(')
  const close = text.indexOf(')')

  assert.deepEqual(
    sourceAnchorRange([
      anchor('s1:i30', open, open + 1),
      anchor('s1:i30', close, close + 1),
    ], text),
    { start: open, end: close + 1 },
  )
})

test('shared source selection never spans different parts', () => {
  const text = [
    '// @part 1 name="高音"',
    '1=C',
    '4/4',
    '1 |',
    '// @part 2 name="低音"',
    '1=C',
    '4/4',
    '5 |',
  ].join('\n')
  const first = text.indexOf('1 |')
  const second = text.indexOf('5 |')

  assert.deepEqual(
    sourceAnchorRange([
      anchor('collision', first, first + 1),
      anchor('collision', second, second + 1),
    ], text),
    { start: first, end: first + 1 },
  )
})
