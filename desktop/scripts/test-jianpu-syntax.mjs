import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/renderer/src/utils/jianpuSyntax.ts')
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourcePath,
}).outputText
const jianpuSyntax = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('ending house tokens classify as ending', () => {
  for (const token of ['{1.}', '{2}', '{1,2.}', '{1，2.}', '{1, 2.}', '{.}']) {
    const tokens = jianpuSyntax.tokenizeJianpuLine(`| ${token} 1 2 |`)
    const house = tokens.find((item) => item.text === token)
    assert.ok(house, `${token} should survive tokenizing`)
    assert.equal(house.type, 'ending', `${token} should classify as ending`)
  }
})

test('ending tokens stay intact next to other syntax', () => {
  const tokens = jianpuSyntax.tokenizeJianpuLine('|: 1 2 3 4 | {1.} 5 6 5 4 :| {2.} 7 1\' |')
  const types = new Map(tokens.filter((t) => t.text.trim()).map((t) => [t.text, t.type]))
  assert.equal(types.get('|:'), 'barline')
  assert.equal(types.get(':|'), 'barline')
  assert.equal(types.get('{1.}'), 'ending')
  assert.equal(types.get('{2.}'), 'ending')
  assert.equal(types.get("1'"), 'note')
})

test('dotted notes and measure labels are not endings', () => {
  for (const token of ['1.', 'q2.', '10.']) {
    const tokens = jianpuSyntax.tokenizeJianpuLine(`${token} |`)
    assert.notEqual(tokens[0].type, 'ending', `${token} must not be an ending`)
  }
})
