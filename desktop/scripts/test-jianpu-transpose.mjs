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

const { detectKeyChanges, classifyKeyEdit, remapOffset } = transpose

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

test('classifyKeyEdit separates a real key change from typing intermediates', () => {
  assert.equal(classifyKeyEdit('1=C\n1 2', '1=G\n1 2'), 'transposable')
  assert.equal(classifyKeyEdit('1=C\n1 2', '1=C\n1 2 |\n1=G\n3 4'), 'transposable')
  // Deleting the only key leaves nothing for the backend to anchor on.
  assert.equal(classifyKeyEdit('1=C\n1 2 |\n1=G\n3 4', '1=C\n1 2'), 'transposable')
  assert.equal(classifyKeyEdit('1=C\n1 2', '1=\n1 2'), 'no-key')
  assert.equal(classifyKeyEdit('1=C\n1 2', '1=C\n1 2 3'), 'unchanged')
  assert.equal(classifyKeyEdit('1=C\n1 2', '1=C\n1 2'), 'unchanged')
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

// The gate is the regression guard for two silent failures: the editor used to
// reset its baseline from a watcher on modelValue, and takePending used to clear
// the baseline before deciding whether to dispatch — so every typing intermediate
// (1=C -> 1= -> 1=D, or 1=E before its trailing space) burned the pre-edit text.
function newGate() {
  return new AutoTransposeGate(classifyKeyEdit)
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

test('gate keeps the baseline when the verdict is unchanged', () => {
  // Scenario 2: typing "1=E" one character at a time. Every intermediate reads
  // as unchanged, and the baseline must survive all of them so the final space
  // dispatches with the original parseable document as previous_text.
  const gate = newGate()
  const original = '1=C\n4/4\n1 2 3 4 | 5 6 7 1 |'
  const states = [
    '1=C\n4/4\n1 2 3 4 | 15 6 7 1 |',
    '1=C\n4/4\n1 2 3 4 | 1=5 6 7 1 |',
    '1=C\n4/4\n1 2 3 4 | 1=E5 6 7 1 |',
  ]
  let before = original
  for (const state of states) {
    gate.recordEdit(before, state)
    assert.equal(gate.takePending(state), null, `dispatched too early at ${state}`)
    assert.ok(gate.hasPendingEdit, `baseline lost at ${state}`)
    before = state
  }
  const final = '1=C\n4/4\n1 2 3 4 | 1=E 5 6 7 1 |'
  gate.recordEdit(before, final)
  assert.deepEqual(gate.takePending(final), { baseline: original, text: final })
})

test('gate keeps the baseline when the new text has no key left', () => {
  // Scenario 1: delete the "C" of "1=C", pause past the debounce, then type "D".
  // The keyless intermediate used to burn a request and the baseline, leaving the
  // second cycle with no old key to transpose from.
  const gate = newGate()
  gate.recordEdit('1=C\n4/4\n1 2 3 4', '1=\n4/4\n1 2 3 4')
  assert.equal(gate.takePending('1=\n4/4\n1 2 3 4'), null)
  assert.ok(gate.hasPendingEdit)
  gate.recordEdit('1=\n4/4\n1 2 3 4', '1=D\n4/4\n1 2 3 4')
  assert.deepEqual(gate.takePending('1=D\n4/4\n1 2 3 4'), {
    baseline: '1=C\n4/4\n1 2 3 4',
    text: '1=D\n4/4\n1 2 3 4',
  })
})

test('gate discards the edit when the text was replaced externally meanwhile', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  assert.equal(gate.takePending('1=D\nsomething else'), null)
  assert.equal(gate.hasPendingEdit, false)
})

test('gate discards a net no-op edit', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=C\n1 2 3')
  assert.equal(gate.takePending('1=C\n1 2 3'), null)
  assert.equal(gate.hasPendingEdit, false)
})

test('gate clears the pending baseline once a request is dispatched', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  assert.ok(gate.hasPendingEdit)
  gate.takePending('1=G\n1 2 3')
  assert.equal(gate.hasPendingEdit, false)
  assert.equal(gate.takePending('1=G\n1 2 3'), null)
})

test('rollbackRequest returns the dispatched baseline for the next round', () => {
  // The backend skipped (parse error, deleted key, no-op), so the pre-edit text
  // is still the only record of the old key and must come back.
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  const dispatched = gate.takePending('1=G\n1 2 3')
  const id = gate.beginRequest()
  assert.equal(gate.hasPendingEdit, false)
  gate.rollbackRequest(id)
  assert.ok(gate.hasPendingEdit)
  gate.recordEdit('1=G\n1 2 3', '1=D\n1 2 3')
  assert.deepEqual(gate.takePending('1=D\n1 2 3'), {
    baseline: dispatched.baseline,
    text: '1=D\n1 2 3',
  })
})

test('commitRequest drops the dispatched baseline so rollback cannot revive it', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  gate.takePending('1=G\n1 2 3')
  const id = gate.beginRequest()
  gate.commitRequest()
  gate.rollbackRequest(id)
  assert.equal(gate.hasPendingEdit, false)
})

test('rollbackRequest does not clobber a newer baseline typed during the request', () => {
  // Keystrokes landing mid-flight record a baseline closer to the current
  // document; the older dispatched one must not overwrite it.
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  gate.takePending('1=G\n1 2 3')
  const id = gate.beginRequest()
  gate.recordEdit('1=G\n1 2 3', '1=G\n1 2 3 4')
  gate.rollbackRequest(id)
  gate.recordEdit('1=G\n1 2 3 4', '1=D\n1 2 3 4')
  assert.deepEqual(gate.takePending('1=D\n1 2 3 4'), {
    baseline: '1=G\n1 2 3',
    text: '1=D\n1 2 3 4',
  })
})

test('rollbackRequest for a superseded request leaves the newer one alone', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  gate.takePending('1=G\n1 2 3')
  const stale = gate.beginRequest()
  const fresh = gate.beginRequest()
  gate.rollbackRequest(stale)
  assert.equal(gate.hasPendingEdit, false, 'stale rollback must not restore')
  gate.rollbackRequest(fresh)
  assert.ok(gate.hasPendingEdit)
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

test('gate reset drops pending edits, dispatched baseline and in-flight responses', () => {
  const gate = newGate()
  gate.recordEdit('1=C\n1 2 3', '1=G\n1 2 3')
  gate.takePending('1=G\n1 2 3')
  const id = gate.beginRequest()
  gate.reset()
  assert.equal(gate.hasPendingEdit, false)
  gate.rollbackRequest(id)
  assert.equal(gate.hasPendingEdit, false, 'reset must also clear dispatched')
  assert.equal(gate.acceptResponse(id, '1=G\n1 2 3', '1=G\n1 2 3'), false)
})
