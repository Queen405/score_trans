import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(here, '../src/renderer/src/utils/zoomFit.ts')
const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  fileName: sourcePath,
}).outputText
const { calculateZoomFit } = await import(
  `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
)

test('content fit centers the padded content in SVG coordinates', () => {
  const result = calculateZoomFit({ x: 100, y: 200, width: 600, height: 200 }, 400, 400, 20)
  assert.deepEqual(result, { scale: 0.625, tx: -50, ty: 12.5 })
})

test('fit never enlarges small content beyond 100 percent', () => {
  const result = calculateZoomFit({ x: 10, y: 20, width: 100, height: 50 }, 800, 600, 24)
  assert.equal(result.scale, 1)
  assert.equal(result.tx, 340)
  assert.equal(result.ty, 255)
})

test('page fit uses the full page and rejects empty measurements', () => {
  assert.deepEqual(
    calculateZoomFit({ x: 0, y: 0, width: 1240, height: 1754 }, 620, 877),
    { scale: 0.5, tx: 0, ty: 0 },
  )
  assert.equal(calculateZoomFit({ x: 0, y: 0, width: 0, height: 10 }, 100, 100), null)
})
