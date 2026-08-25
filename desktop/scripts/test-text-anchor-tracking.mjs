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
const { reconcileTextAnchors, trackTextAnchors } = await import(moduleUrl)

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
