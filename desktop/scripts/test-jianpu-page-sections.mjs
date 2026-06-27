import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/jianpuPageSections.ts',
)
const source = fs.readFileSync(sourcePath, 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourcePath,
}).outputText
const utils = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('page sections preserve comments and blank lines', () => {
  const text = utils.composeJianpuPageText([
    {
      inputFileName: '第一页.png',
      startMeasureNumber: 5,
      jianpuText: '1=C\n\n// 注释\n1 2 3 4 |',
    },
    {
      inputFileName: '第二页.png',
      jianpuText: '5 6 7 1 |\n',
    },
  ])
  const sections = utils.parseJianpuPageSections(text)

  assert.equal(sections.length, 2)
  assert.equal(sections[0].body, '1=C\n\n// 注释\n1 2 3 4 |')
  assert.equal(sections[1].body, '5 6 7 1 |\n')
  assert.equal(sections[0].startMeasureNumber, 5)
  assert.equal(sections[1].startMeasureNumber, null)
})

test('legacy merged text migrates to explicit page markers', () => {
  const pages = [
    { inputFileName: 'p1.png', startMeasureNumber: 9, jianpuText: '1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '3 4 |' },
  ]
  const migrated = utils.migrateLegacyJianpuPageText('1 2 |\n\n3 4 |', pages)

  assert.match(migrated, /^\/\/ @page 1 start=9 name="p1\.png"/)
  assert.match(migrated, /\/\/ @page 2 start=auto name="p2\.png"/)
  assert.deepEqual(
    utils.parseJianpuPageSections(migrated).map((section) => section.body),
    ['1 2 |', '3 4 |'],
  )
})

test('measure ranges continue across automatic page starts', () => {
  const text = utils.composeJianpuPageText([
    { startMeasureNumber: 5, jianpuText: '1 2 |\n3 4 |' },
    { jianpuText: '5 6 | *3' },
  ])
  const summaries = utils.jianpuPageSummaries(text, 1)

  assert.deepEqual(
    summaries.map((summary) => [
      summary.startMeasureNumber,
      summary.endMeasureNumber,
      summary.measureCount,
    ]),
    [[5, 6, 2], [7, 9, 3]],
  )
})

test('gutter labels show page markers and continuous measure numbers', () => {
  const text = utils.composeJianpuPageText([
    { startMeasureNumber: 12, jianpuText: '1 2 |' },
    { jianpuText: '// 普通注释\n3 4 |' },
  ])

  assert.deepEqual(
    utils.jianpuGutterLabels(text, 1).filter(Boolean),
    ['P1', '12', 'P2', '13'],
  )
})

test('updating the first start measure changes only its marker', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', startMeasureNumber: 1, jianpuText: '1 |' },
    { inputFileName: 'p2.png', jianpuText: '2 |' },
  ])
  const updated = utils.updateJianpuPageStart(text, 0, 20)
  const sections = utils.parseJianpuPageSections(updated)

  assert.equal(sections[0].startMeasureNumber, 20)
  assert.equal(sections[1].startMeasureNumber, null)
  assert.equal(sections[1].body, '2 |')
})

test('removing a page removes its body and renumbers following markers', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1 |' },
    { inputFileName: 'p2.png', jianpuText: '2 |' },
    { inputFileName: 'p3.png', jianpuText: '3 |' },
  ])
  const updated = utils.removeJianpuPageSection(text, 1)
  const sections = utils.parseJianpuPageSections(updated)

  assert.deepEqual(sections.map((section) => section.body), ['1 |', '3 |'])
  assert.deepEqual(sections.map((section) => section.pageIndex), [0, 1])
  assert.match(updated, /\/\/ @page 2 start=auto name="p3\.png"/)
})
