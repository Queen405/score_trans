import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

function compile(source) {
  return ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText
}

function moduleUrl(javascript) {
  return `data:text/javascript;base64,${Buffer.from(javascript).toString('base64')}`
}

// Inline the relative import graph so each module can be loaded as a data: URL.
const inlinedByPath = new Map()

async function inlineModule(relativePath) {
  const url = new URL(relativePath, import.meta.url)
  const cached = inlinedByPath.get(url.href)
  if (cached) return cached
  let source = await readFile(url, 'utf8')
  const specifiers = new Set(
    Array.from(source.matchAll(/from '(\.[^']+)'/g), (match) => match[1]),
  )
  for (const specifier of specifiers) {
    const dependency = await inlineModule(new URL(`${specifier}.ts`, url).href)
    source = source.replaceAll(`from '${specifier}'`, `from '${dependency}'`)
  }
  const inlined = moduleUrl(compile(source))
  inlinedByPath.set(url.href, inlined)
  return inlined
}

async function loadModule(relativePath) {
  return import(await inlineModule(relativePath))
}

const transpose = await loadModule('../src/renderer/src/utils/jianpuTranspose.ts')
const { AutoTransposeGate } = await loadModule('../src/renderer/src/utils/autoTransposeGate.ts')

const { detectKeyChanges, hasKeyChange, remapOffset } = transpose

test('detectKeyChanges finds line-start, inline and multi-character keys', () => {
  assert.deepEqual(detectKeyChanges('1=C\n1 2 3'), [{ lineIndex: 0, key: 'C' }])
  assert.deepEqual(detectKeyChanges('1 2 | 1=G 3 4'), [{ lineIndex: 0, key: 'G' }])
  assert.deepEqual(detectKeyChanges('1=Bb\n1=F#'), [
    { lineIndex: 0, key: 'Bb' },
    { lineIndex: 1, key: 'F#' },
  ])
})

test('detectKeyChanges ignores keys inside comments and lyric lines', () => {
  assert.deepEqual(detectKeyChanges('1=C\n1 2 3 // 1=G'), [{ lineIndex: 0, key: 'C' }])
  assert.deepEqual(detectKeyChanges('1=C\nL: 1=G b c'), [{ lineIndex: 0, key: 'C' }])
  assert.deepEqual(detectKeyChanges('1=C\n@text 1=G here'), [{ lineIndex: 0, key: 'C' }])
})

test('detectKeyChanges requires the key to be a standalone token', () => {
  assert.deepEqual(detectKeyChanges('x1=G'), [])
  assert.deepEqual(detectKeyChanges('1=Gx'), [])
})

test('hasKeyChange detects value change, insertion and deletion', () => {
  assert.equal(hasKeyChange('1=C\n1 2', '1=G\n1 2'), true)
  assert.equal(hasKeyChange('1=C\n1 2', '1=C\n1 2 |\n1=G\n3 4'), true)
  assert.equal(hasKeyChange('1=C\n1 2 |\n1=G\n3 4', '1=C\n1 2'), true)
  assert.equal(hasKeyChange('1=C\n1 2', '1=C\n1 2 3'), false)
  assert.equal(hasKeyChange('1=C\n1 2', '1=C\n1 2'), false)
})

test('remapOffset keeps a cursor located before the edited region', () => {
  const before = '1=C\n1 2 3\n4 5 6'
  const after = '1=C\n1 2 3\nb7, 1 2'
  assert.equal(remapOffset(before, after, 2), 2)
  assert.equal(remapOffset(before, after, 0), 0)
})

test('remapOffset shifts a cursor located after the edited region', () => {
  const before = 'head\nAAA\ntail'
  const after = 'head\nBBBBBB\ntail'
  const tailIndexBefore = before.indexOf('tail')
  const tailIndexAfter = after.indexOf('tail')
  assert.equal(remapOffset(before, after, tailIndexBefore), tailIndexAfter)
  assert.equal(remapOffset(before, after, before.length), after.length)
})

test('remapOffset clamps a cursor inside the edited region to its end', () => {
  const before = 'head AAA tail'
  const after = 'head BBBBBB tail'
  const inside = before.indexOf('AAA') + 1
  const mapped = remapOffset(before, after, inside)
  assert.equal(after.slice(mapped), ' tail')
})

test('remapOffset is identity when the text did not change', () => {
  assert.equal(remapOffset('same', 'same', 2), 2)
})

test('remapOffset never returns an out-of-range offset', () => {
  const before = '1=C\n1 2 3 4 5'
  const after = '1=G'
  for (let offset = 0; offset <= before.length; offset++) {
    const mapped = remapOffset(before, after, offset)
    assert.ok(mapped >= 0 && mapped <= after.length, `offset ${offset} -> ${mapped}`)
  }
})

// The gate is the regression guard for the bug where the editor reset its
// baseline from a watcher on modelValue, so the pre-edit key was lost and the
// backend was never called.
function newGate() {
  return new AutoTransposeGate(hasKeyChange)
}

test('gate uses the pre-edit text as baseline, not the freshly typed text', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  const pending = gate.takePending('1=G\n1 2 3')
  assert.deepEqual(pending, { baseline: '1=C\n1 2 3', text: '1=G\n1 2 3' })
})

test('gate keeps the earliest baseline across a burst of edits', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=\n1 2 3')
  gate.recordEdit('1=\n1 2 3', '1=G\n1 2 3')
  gate.recordEdit('1=G\n1 2 3', '1=Gb\n1 2 3')
  const pending = gate.takePending('1=Gb\n1 2 3')
  assert.equal(pending.baseline, '1=C\n1 2 3')
  assert.equal(pending.text, '1=Gb\n1 2 3')
})

test('gate skips edits that do not touch any key token', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=C\n1 2 3 4')
  assert.equal(gate.takePending('1=C\n1 2 3 4'), null)
})

test('gate discards the edit when the text was replaced externally meanwhile', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  assert.equal(gate.takePending('1=D\nsomething else'), null)
})

test('gate clears pending state after takePending regardless of outcome', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  assert.ok(gate.hasPendingEdit)
  gate.takePending('1=G\n1 2 3')
  assert.equal(gate.hasPendingEdit, false)
  assert.equal(gate.takePending('1=G\n1 2 3'), null)
})

test('gate rejects a stale response when a newer request was started', () => {
  const gate = newGate()
  const first = gate.beginRequest()
  const second = gate.beginRequest()
  assert.equal(gate.acceptResponse(first, 'text', 'text'), false)
  assert.equal(gate.acceptResponse(second, 'text', 'text'), true)
})

test('gate rejects a response whose request text is no longer current', () => {
  const gate = newGate()
  const id = gate.beginRequest()
  assert.equal(gate.acceptResponse(id, '1=G\n1 2 3', '1=G\n1 2 3 4'), false)
})

test('gate reset drops pending edits and invalidates in-flight responses', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  const id = gate.beginRequest()
  gate.reset()
  assert.equal(gate.hasPendingEdit, false)
  assert.equal(gate.takePending('1=G\n1 2 3'), null)
  assert.equal(gate.acceptResponse(id, '1=G\n1 2 3', '1=G\n1 2 3'), false)
})

test('gate ignores a no-op edit where before equals after', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=C\n1 2 3')
  assert.equal(gate.takePending('1=C\n1 2 3'), null)
})
