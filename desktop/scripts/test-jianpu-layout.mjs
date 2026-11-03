import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/renderer/src/utils/jianpuLayout.ts')
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourcePath,
}).outputText
const layout = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('layout key is stable and ordered by render meaning', () => {
  assert.equal(layout.PUBLICATION_ENGINE_VERSION, 'publication-24')
  assert.equal(layout.jianpuLayoutKey(67, 92, 90, 100, false, 0), '67:92:90:100:0:a')
  assert.equal(layout.jianpuLayoutKey(75, 88, 85, 120, false, 4), '75:88:85:120:0:4')
  assert.equal(layout.jianpuLayoutKey(67, 92, 90, 100, true, 0), '67:92:90:100:1:a')
  assert.equal(
    layout.jianpuLayoutKey(67, 92, 90, 100, false, 4, '10:7:12:12:5:2'),
    '67:92:90:100:0:4:10:7:12:12:5:2',
  )
})

test('missing or different layout keys make cached A4 output stale', () => {
  assert.equal(layout.isRenderLayoutStale('', '67:92:90:100'), true)
  assert.equal(layout.isRenderLayoutStale('75:88:85:100', '67:92:90:100'), true)
  assert.equal(layout.isRenderLayoutStale('67:92:90', '67:92:90:100'), true)
  assert.equal(layout.isRenderLayoutStale('67:92:90:100', '67:92:90:100'), false)
})
