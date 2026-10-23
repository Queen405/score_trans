import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { i18nStubUrl } from './lib/i18n-stub.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/jianpuPageSections.ts',
)
const syntaxSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/jianpuSyntax.ts',
)
const syntaxCompiled = ts.transpileModule(fs.readFileSync(syntaxSourcePath, 'utf8'), {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: syntaxSourcePath,
}).outputText
const syntaxModuleUrl = `data:text/javascript;base64,${Buffer.from(syntaxCompiled).toString('base64')}`
const source = fs.readFileSync(sourcePath, 'utf8').replace(
  "from './jianpuSyntax'",
  `from '${syntaxModuleUrl}'`,
)
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: sourcePath,
}).outputText
const utilsModuleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
const utils = await import(utilsModuleUrl)

test('live page-marker helpers tolerate every character-typing intermediate', () => {
  const prefixes = ['/', '//', '// ', '// @', '// @p', '// @pa', '// @pag', '// @page', '// @page ']
  for (const text of prefixes) {
    assert.doesNotThrow(() => utils.hasLiveJianpuPageMarkers(text), text)
    assert.doesNotThrow(() => utils.jianpuGutterLabels(text), text)
    assert.doesNotThrow(() => utils.jianpuPageSummaries(text), text)
    assert.equal(utils.hasLiveJianpuPageMarkers(text), false, text)
  }

  assert.throws(
    () => utils.parseJianpuPageMarker('// @page'),
    /无效的分页标记/,
    'strict parsing must still reject an incomplete persisted marker',
  )
  assert.throws(() => utils.hasJianpuPageMarkers('// @page'), /无效的分页标记/)
  assert.equal(utils.hasLiveJianpuPageMarkers('// @page 1'), true)
})

test('plain-comment mode masks page and part markers without shifting offsets', () => {
  const text = [
    '\ufeff  //\t@page 1 name="p.png"',
    '// @part 1 name="A"',
    '// @page',
    '// ordinary comment',
    '1 2 3 4 | // @page 9',
    '// @pages 2',
  ].join('\r\n')

  const masked = utils.maskJianpuStructureMarkers(text)

  assert.equal(masked.length, text.length)
  assert.deepEqual(
    Array.from(masked, (character, index) => character === '\n' || character === '\r' ? index : -1)
      .filter((index) => index >= 0),
    Array.from(text, (character, index) => character === '\n' || character === '\r' ? index : -1)
      .filter((index) => index >= 0),
  )
  assert.match(masked, /^\ufeff  \/\/\t page 1 name="p\.png"/)
  assert.match(masked, /^\/\/  part 1 name="A"/m)
  assert.match(masked, /^\/\/  page$/m)
  assert.match(masked, /^\/\/ ordinary comment$/m)
  assert.match(masked, /1 2 3 4 \| \/\/ @page 9/)
  assert.match(masked, /^\/\/ @pages 2$/m)
  assert.equal(utils.hasLiveJianpuPageMarkers(masked), false)
  assert.equal(utils.parseJianpuPageSections(masked).length, 1)
})

const jianpuTextStateSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/jianpuTextState.ts',
)
const textDiffSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/textDiff.ts',
)
const textDiffSource = fs.readFileSync(textDiffSourcePath, 'utf8')
const textDiffCompiled = ts.transpileModule(textDiffSource, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: textDiffSourcePath,
}).outputText
const textDiffUrl = `data:text/javascript;base64,${Buffer.from(textDiffCompiled).toString('base64')}`
const jianpuTextStateSource = fs.readFileSync(jianpuTextStateSourcePath, 'utf8').replace(
  "from './textDiff'",
  `from '${textDiffUrl}'`,
)
const jianpuTextStateCompiled = ts.transpileModule(jianpuTextStateSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: jianpuTextStateSourcePath,
}).outputText
const jianpuTextState = await import(
  `data:text/javascript;base64,${Buffer.from(jianpuTextStateCompiled).toString('base64')}`
)

const editorViewportSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/editorViewport.ts',
)
const editorViewportSource = fs.readFileSync(editorViewportSourcePath, 'utf8')
const editorViewportCompiled = ts.transpileModule(editorViewportSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: editorViewportSourcePath,
}).outputText
const editorViewport = await import(
  `data:text/javascript;base64,${Buffer.from(editorViewportCompiled).toString('base64')}`
)

const batchRenderSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/batchRender.ts',
)
const batchRenderSource = fs.readFileSync(batchRenderSourcePath, 'utf8')
const batchRenderCompiled = ts.transpileModule(batchRenderSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: batchRenderSourcePath,
}).outputText.replace(
  "from './jianpuPageSections'",
  `from '${utilsModuleUrl}'`,
)
const batchRender = await import(
  `data:text/javascript;base64,${Buffer.from(batchRenderCompiled).toString('base64')}`
)

const taskStateSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/taskEventState.ts',
)
const taskStateSource = fs.readFileSync(taskStateSourcePath, 'utf8')
const taskStateCompiled = ts.transpileModule(taskStateSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: taskStateSourcePath,
}).outputText
const taskState = await import(
  `data:text/javascript;base64,${Buffer.from(taskStateCompiled).toString('base64')}`
)

const asyncCoordinationSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/asyncCoordination.ts',
)
const asyncCoordinationSource = fs.readFileSync(asyncCoordinationSourcePath, 'utf8')
const asyncCoordinationCompiled = ts.transpileModule(asyncCoordinationSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: asyncCoordinationSourcePath,
}).outputText
const asyncCoordination = await import(
  `data:text/javascript;base64,${Buffer.from(asyncCoordinationCompiled).toString('base64')}`
)

const historyPageStateSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/historyPageState.ts',
)
const historyPageStateSource = fs.readFileSync(historyPageStateSourcePath, 'utf8')
const historyPageStateCompiled = ts.transpileModule(historyPageStateSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: historyPageStateSourcePath,
}).outputText
const historyPageState = await import(
  `data:text/javascript;base64,${Buffer.from(historyPageStateCompiled).toString('base64')}`
)

const recognitionHistorySourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/recognitionHistory.ts',
)
const recognitionHistorySource = fs.readFileSync(recognitionHistorySourcePath, 'utf8')
const recognitionHistoryCompiled = ts.transpileModule(recognitionHistorySource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: recognitionHistorySourcePath,
}).outputText
const recognitionHistory = await import(
  `data:text/javascript;base64,${Buffer.from(recognitionHistoryCompiled).toString('base64')}`
)

const apiClientSourcePath = path.resolve(
  here,
  '../src/renderer/src/api/client.ts',
)
const apiClientSource = fs.readFileSync(apiClientSourcePath, 'utf8')
const apiClientCompiled = ts.transpileModule(apiClientSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: apiClientSourcePath,
}).outputText.replace("from '../i18n'", `from '${i18nStubUrl}'`)
const apiClient = await import(
  `data:text/javascript;base64,${Buffer.from(apiClientCompiled).toString('base64')}`
)

const ocrTextSourcePath = path.resolve(
  here,
  '../src/renderer/src/utils/ocrText.ts',
)
const ocrTextSource = fs.readFileSync(ocrTextSourcePath, 'utf8')
const ocrTextCompiled = ts.transpileModule(ocrTextSource, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: ocrTextSourcePath,
}).outputText
const ocrText = await import(
  `data:text/javascript;base64,${Buffer.from(ocrTextCompiled).toString('base64')}`
)

const recognizeViewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/views/RecognizeView.vue'),
  'utf8',
)
const convertViewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/views/ConvertView.vue'),
  'utf8',
)
const jianpuEditorSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/JianpuEditor.vue'),
  'utf8',
)
const historySavePayloadSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/utils/historySavePayload.ts'),
  'utf8',
)
const correctApiSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/api/correct.ts'),
  'utf8',
)
const originalPreviewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/OriginalPreview.vue'),
  'utf8',
)
const svgPreviewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/PublicationPreview.vue'),
  'utf8',
)
const historyQuickEntrySource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/HistoryQuickEntry.vue'),
  'utf8',
)
const efficiencyDashboardSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/EfficiencyDashboard.vue'),
  'utf8',
)
const assistantStoreSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/stores/assistant.ts'),
  'utf8',
)

test('assistant session deletion reports failures before mutating local state', () => {
  const match = assistantStoreSource.match(
    /async function deleteSession[\s\S]*?\n  }\n\n  async function send/,
  )
  assert.ok(match, 'deleteSession implementation should be present')

  const handler = match[0]
  assert.match(handler, /loading\.value\s*=\s*true/)
  assert.match(handler, /error\.value\s*=\s*''/)
  assert.match(
    handler,
    /try\s*\{[\s\S]*await requireData\(aiApi\.deleteChatSession\(sessionId\)\)/,
  )
  assert.match(
    handler,
    /catch \(e: unknown\)[\s\S]*error\.value\s*=\s*e instanceof Error/,
  )
  assert.match(handler, /finally\s*\{[\s\S]*loading\.value\s*=\s*false/)
  assert.ok(
    handler.indexOf('await requireData(aiApi.deleteChatSession(sessionId))')
      < handler.indexOf('sessions.value = sessions.value.filter'),
    'local session state must only change after the backend confirms deletion',
  )
})

test('page sections preserve comments and blank lines', () => {
  const text = utils.composeJianpuPageText([
    {
      inputFileName: '第一页.png',
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
  assert.equal(sections[0].inputFileName, '第一页.png')
  assert.equal(sections[1].inputFileName, '第二页.png')
})

test('page section body offsets locate the second page body in UTF-16 coordinates', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: '第一页.png', jianpuText: '1=C\n1 2 |' },
    { inputFileName: '第二页.png', jianpuText: '1=G\n7 1 |' },
  ])
  const sections = utils.parseJianpuPageSections(text)
  const offset = utils.jianpuPageSectionBodyOffset(text, sections, 1)

  assert.equal(text.slice(offset, offset + 3), '1=G')
  assert.equal(text.slice(offset).indexOf('7'), 4)
})

test('page section body offsets preserve lone CR line endings', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '1=G\n7 1 |' },
  ]).replaceAll('\n', '\r')
  const sections = utils.parseJianpuPageSections(text)
  const offset = utils.jianpuPageSectionBodyOffset(text, sections, 1)

  assert.equal(text.slice(offset, offset + 3), '1=G')
})

test('legacy merged text migrates to explicit page markers', () => {
  const pages = [
    { inputFileName: 'p1.png', jianpuText: '1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '3 4 |' },
  ]
  const migrated = utils.migrateLegacyJianpuPageText('1 2 |\n\n3 4 |', pages)

  assert.match(migrated, /^\/\/ @page 1 name="p1\.png"/)
  assert.match(migrated, /\/\/ @page 2 name="p2\.png"/)
  assert.deepEqual(
    utils.parseJianpuPageSections(migrated).map((section) => section.body),
    ['1 2 |', '3 4 |'],
  )
})

test('history restore rebuilds a stale marker-only batch from completed pages', () => {
  const initialPages = [
    { inputFileName: 'p1.png', jianpuText: '' },
    { inputFileName: 'p2.png', jianpuText: '' },
  ]
  const staleBatchText = utils.composeJianpuPageText(initialPages)
  const completedPages = [
    { inputFileName: 'p1.png', jianpuText: '1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '3 4 |' },
  ]

  const restored = utils.restoreJianpuPageText(staleBatchText, completedPages)

  assert.deepEqual(
    utils.parseJianpuPageSections(restored).map((section) => section.body),
    ['1 2 |', '3 4 |'],
  )
})

test('history restore preserves non-empty batch edits over page snapshots', () => {
  const editedBatchText = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '6 6 |' },
    { inputFileName: 'p2.png', jianpuText: '' },
  ])
  const restored = utils.restoreJianpuPageText(editedBatchText, [
    { inputFileName: 'p1.png', jianpuText: '1 2 |' },
    { inputFileName: 'p2.png', jianpuText: '3 4 |' },
  ])

  assert.equal(restored, editedBatchText)
})

test('recognized batch adds one default tempo before all page markers', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n4/4\n1 2 3 4 |' },
    { inputFileName: 'p2.png', jianpuText: '1=C\n4/4\n5 6 7 1 |' },
  ])

  const normalized = utils.ensureRecognizedTempoHeader(text)

  assert.equal(normalized.startsWith('tempo=120\n// @page 1'), true)
  assert.equal(normalized.match(/^tempo=/gm)?.length, 1)
})

test('recognized batch keeps an explicit initial tempo', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: 'tempo=96\n1=C\n4/4\n1 2 3 4 |' },
  ])

  assert.equal(utils.ensureRecognizedTempoHeader(text), text)
})

test('only the first recognized page receives the default tempo header', () => {
  const text = '1=C\n4/4\n1 2 3 4 |'

  assert.equal(utils.ensureRecognizedPageTempoHeader(text, 0), `tempo=120\n${text}`)
  assert.equal(utils.ensureRecognizedPageTempoHeader(text, 1), text)
})

test('recognized batch defaults the start but preserves a later page tempo', () => {
  const text = utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n4/4\n1 2 3 4 |' },
    { inputFileName: 'p2.png', jianpuText: '1=C\n4/4\ntempo=80\n5 6 7 1 |' },
  ])

  const normalized = utils.ensureRecognizedTempoHeader(text)

  assert.equal(normalized.startsWith('tempo=120\n'), true)
  assert.equal(normalized.includes('tempo=80\n5 6 7 1 |'), true)
})

test('recognized multipart batch puts the single default after the first part marker', () => {
  const text = [
    '// @page 1',
    '// @part 1 name="A"',
    '1=C',
    '4/4',
    '1 2 3 4 |',
    '// @part 2 name="B"',
    '1=C',
    '4/4',
    '5 6 7 1 |',
  ].join('\n')

  const normalized = utils.ensureRecognizedTempoHeader(text)

  assert.equal(normalized.startsWith('// @page 1\n// @part 1 name="A"\ntempo=120\n'), true)
  assert.equal(normalized.match(/^tempo=/gm)?.length, 1)
})

test('resetting the first page restores the recognized default tempo', () => {
  const recognized = utils.ensureRecognizedTempoHeader(utils.composeJianpuPageText([
    { inputFileName: 'p1.png', jianpuText: '1=C\n4/4\n1 2 3 4 |' },
    { inputFileName: 'p2.png', jianpuText: '1=C\n4/4\n5 6 7 1 |' },
  ])).replace('tempo=120', 'tempo=80')

  const reset = utils.ensureRecognizedTempoHeader(utils.replaceJianpuSectionBody(
    recognized,
    0,
    '1=C\n4/4\n1 2 3 4 |',
    { inputFileName: 'p1.png' },
  ))

  assert.equal(reset.includes('tempo=80'), false)
  assert.equal(reset.match(/^tempo=120$/gm)?.length, 1)
})

test('measure ranges continue across pages', () => {
  const text = utils.composeJianpuPageText([
    { jianpuText: '1 2 |\n3 4 |' },
    { jianpuText: '5 6 | *3' },
  ])
  const summaries = utils.jianpuPageSummaries(text)

  assert.deepEqual(
    summaries.map((summary) => [
      summary.firstMeasureNumber,
      summary.lastMeasureNumber,
      summary.measureCount,
    ]),
    [[1, 2, 2], [3, 5, 3]],
  )
})

test('measure ranges honor a custom batch starting number', () => {
  const text = utils.composeJianpuPageText([
    { jianpuText: '1 2 |' },
    { jianpuText: '3 4 |' },
  ])

  assert.deepEqual(
    utils.jianpuPageSummaries(text, 5).map((summary) => [
      summary.firstMeasureNumber,
      summary.lastMeasureNumber,
    ]),
    [[5, 5], [6, 6]],
  )
  assert.deepEqual(
    utils.jianpuGutterLabels(text, 5).filter(Boolean),
    ['P1', '5', 'P2', '6'],
  )
})

test('multi-part page ranges count shared measure slots only once', () => {
  const firstPage = [
    '// @part 1 name="高音"',
    '1=C',
    '4/4',
    '1 |',
    '2 |',
    '// @part 2 name="低音"',
    '1=C',
    '4/4',
    '5 |',
    '6 |',
  ].join('\n')
  const secondPage = [
    '// @part 1 name="高音"',
    '1=C',
    '4/4',
    '3 |',
    '4 |',
    '// @part 2 name="低音"',
    '1=C',
    '4/4',
    '7 |',
    "1' |",
  ].join('\n')
  const text = utils.composeJianpuPageText([
    { jianpuText: firstPage },
    { jianpuText: secondPage },
  ])

  assert.deepEqual(
    utils.jianpuPageSummaries(text).map((summary) => [
      summary.firstMeasureNumber,
      summary.lastMeasureNumber,
      summary.measureCount,
    ]),
    [[1, 2, 2], [3, 4, 2]],
  )
})

test('gutter labels show page markers and continuous measure numbers', () => {
  const text = utils.composeJianpuPageText([
    { jianpuText: '1 2 |' },
    { jianpuText: '// 普通注释\n3 4 |' },
  ])

  assert.deepEqual(
    utils.jianpuGutterLabels(text).filter(Boolean),
    ['P1', '1', 'P2', '2'],
  )
})

test('lyric block lines show their covered measure numbers and never advance the score', () => {
  const text = '1 2 3 4 | 5 6 7 1 |\n/L: 春 眠 | 晓 闻/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-2', '1-2', ''])
  assert.equal(utils.jianpuMeasureCount(text), 2)
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
  assert.match(updated, /\/\/ @page 2 name="p3\.png"/)
})

test('completed task events bypass the progress callback', () => {
  let progressCalls = 0
  const disposition = taskState.dispatchTaskProgress(
    { status: 'completed' },
    () => {
      progressCalls += 1
      throw new Error('terminal events must not be reported as progress')
    },
  )

  assert.equal(disposition, 'completed')
  assert.equal(progressCalls, 0)
})

test('running task events still reach the progress callback', () => {
  let receivedStatus = ''
  const disposition = taskState.dispatchTaskProgress(
    { status: 'running' },
    (event) => {
      receivedStatus = event.status
    },
  )

  assert.equal(disposition, 'progress')
  assert.equal(receivedStatus, 'running')
})

test('page updates with the same id execute in submission order', async () => {
  const queue = asyncCoordination.createKeyedAsyncQueue()
  const events = []
  let releaseWaiting
  const waitingGate = new Promise((resolve) => {
    releaseWaiting = resolve
  })

  const waiting = queue.enqueue(17, async () => {
    events.push('waiting:start')
    await waitingGate
    events.push('waiting:end')
    return 'waiting'
  })
  const completed = queue.enqueue(17, async () => {
    events.push('completed:start')
    events.push('completed:end')
    return 'completed'
  })

  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(events, ['waiting:start'])

  releaseWaiting()
  assert.deepEqual(await Promise.all([waiting, completed]), ['waiting', 'completed'])
  assert.deepEqual(events, [
    'waiting:start',
    'waiting:end',
    'completed:start',
    'completed:end',
  ])
})

test('a failed page update does not block the next update', async () => {
  const queue = asyncCoordination.createKeyedAsyncQueue()
  const failed = queue.enqueue(23, async () => {
    throw new Error('network failed')
  })
  const completed = queue.enqueue(23, async () => 'completed')

  await assert.rejects(failed, /network failed/)
  assert.equal(await completed, 'completed')
})

test('invalidating a request epoch rejects an older history snapshot', () => {
  const epoch = asyncCoordination.createRequestEpoch()
  const staleRequest = epoch.begin()

  epoch.invalidate()

  assert.equal(epoch.isCurrent(staleRequest), false)
  const currentRequest = epoch.begin()
  assert.equal(epoch.isCurrent(currentRequest), true)
})

test('partial recognition snapshots every source page in stable order', () => {
  const pages = Array.from({ length: 10 }, (_, index) => ({
    id: `page-${index + 1}`,
    inputFileName: `第${index + 1}页.png`,
    inputFileId: `input-${index + 1}`,
    originalFileId: '',
    musicxmlFileId: '',
    jianpuText: '',
    ocrText: '',
    svgFileId: '',
    startMeasureNumber: null,
  }))

  const snapshot = recognitionHistory.buildHistoryBatchSnapshot(
    pages,
    new Set(['page-2', 'page-7']),
  )

  assert.deepEqual(snapshot.pageIds, pages.map((page) => page.id))
  assert.equal(snapshot.pages.length, 10)
  assert.equal(snapshot.pages[1].status, 'processing')
  assert.equal(snapshot.pages[6].status, 'processing')
  assert.equal(
    snapshot.pages.filter((page) => page.status === 'unrecognized').length,
    8,
  )
  assert.equal(snapshot.pages[9].input_file_id, 'input-10')
})

test('recognition resolves a restored batch through the stable history page id', () => {
  const restoredPages = [
    { id: 'restored-1', batchId: 'restored-batch', historyPageId: 101 },
    { id: 'restored-2', batchId: 'restored-batch', historyPageId: 102 },
  ]

  const batchPages = recognitionHistory.recognitionBatchPagesForPage(
    restoredPages,
    'original-1',
    101,
  )

  assert.deepEqual(batchPages.map((page) => page.id), ['restored-1', 'restored-2'])
})

test('unrecognized pages are neutral for completed-batch rendering', () => {
  assert.equal(
    recognitionHistory.isRecognitionBatchReadyForRender([
      'completed',
      'unrecognized',
      'unrecognized',
    ]),
    true,
  )
  assert.equal(
    recognitionHistory.isRecognitionBatchReadyForRender([
      'unrecognized',
      'unrecognized',
    ]),
    false,
  )
  for (const blockingStatus of ['pending', 'processing', 'waiting', 'failed']) {
    assert.equal(
      recognitionHistory.isRecognitionBatchReadyForRender([
        'completed',
        blockingStatus,
        'unrecognized',
      ]),
      false,
    )
  }
})

test('partial recognition keeps page markers for every source page', () => {
  const text = utils.composeJianpuPageText(
    Array.from({ length: 10 }, (_, index) => ({
      inputFileName: `page-${index + 1}.png`,
      jianpuText: index === 1 || index === 6 ? '1 2 3 4 |' : '',
    })),
  )

  assert.equal(utils.parseJianpuPageSections(text).length, 10)
  assert.deepEqual(
    utils.jianpuGutterLabels(text).filter((label) => label.startsWith('P')),
    Array.from({ length: 10 }, (_, index) => `P${index + 1}`),
  )
})

test('resetting Jianpu replaces the source provenance snapshot', () => {
  const resetStart = convertViewSource.indexOf('async function resetAll')
  const resetEnd = convertViewSource.indexOf('async function toggleEditMode', resetStart)
  const resetHandler = convertViewSource.slice(resetStart, resetEnd)

  assert.match(resetHandler, /textAnchors:\s*textAnchorBaselineAnchors\.map/)
  assert.match(resetHandler, /textAnchorBaselineText:\s*resetJianpuText/)
  assert.match(resetHandler, /textHash:\s*await hashJianpuText\(resetJianpuText\)/)
  assert.match(resetHandler, /jianpuDirty:\s*false/)
  assert.match(resetHandler, /deletedSourceIds:\s*\[\]/)
})

test('marker correction uses the registered backend route and persists source state', () => {
  assert.match(correctApiSource, /const BASE = '\/correct'/)
  assert.doesNotMatch(correctApiSource, /\/api\/correct/)
  assert.match(convertViewSource, /workspacePersistence\.saveBatch/)
  assert.match(historySavePayloadSource, /omr_file_id:\s*page\.omrFileId/)
  assert.match(historySavePayloadSource, /deleted_source_ids:\s*page\.deletedSourceIds/)
  assert.doesNotMatch(historySavePayloadSource, /source_map_file_id:\s*[^,]+\|\|\s*undefined/)
})

test('marker correction preserves dirty Jianpu text instead of replacing it', () => {
  assert.match(convertViewSource, /hasJianpuTextEdits\(/)
  assert.match(convertViewSource, /preserveEditedJianpuText/)
  assert.match(convertViewSource, /reconcileTextAnchors\([\s\S]*data\.text_anchors/)
  assert.match(convertViewSource, /textAnchorBaselineText:/)
  assert.match(convertViewSource, /textAnchorBaselineAnchors[:,]/)
})

test('Jianpu edit detection survives history restore through the canonical text hash', async () => {
  const canonical = '1=C\n4/4\n1 2 3 4 |'
  const edited = '1=C\n4/4\n1 2 3 4 |\n// 用户编辑'
  const canonicalHash = await jianpuTextState.hashJianpuText(canonical)

  assert.equal(
    await jianpuTextState.hasJianpuTextEdits(canonical, canonical, canonicalHash),
    false,
  )
  assert.equal(
    await jianpuTextState.hasJianpuTextEdits(edited, canonical, canonicalHash),
    true,
  )
  assert.equal(
    await jianpuTextState.hasJianpuTextEdits(edited, edited, canonicalHash),
    true,
  )
  assert.equal(
    jianpuTextState.preserveEditedJianpuText(edited, '1=C\n4/4\n1 2 3 |', true),
    edited,
  )
  assert.equal(
    jianpuTextState.preserveEditedJianpuText(canonical, '1=C\n4/4\n1 2 3 |', false),
    '1=C\n4/4\n1 2 3 |',
  )
})

test('marker correction merges deleted notes into dirty Jianpu text', () => {
  const canonical = '1=C\n4/4\n1 2 3 4 5 |'
  const edited = '1=C\n4/4\n1 2 3 4 6 | // 用户备注'
  const corrected = '1=C\n4/4\n1 3 5 |'

  assert.equal(
    jianpuTextState.preserveEditedJianpuText(
      edited,
      corrected,
      true,
      canonical,
    ),
    '1=C\n4/4\n1 3 6 | // 用户备注',
  )
})

test('large generated corrections preserve user edits outside the diff fallback range', () => {
  const middle = 'a'.repeat(2100)
  const correctedMiddle = 'b'.repeat(2100)
  const baseline = `HEAD|${middle}|TAIL`
  const edited = `USER|${middle}|TAIL`
  const generated = `HEAD|${correctedMiddle}|TAIL`

  assert.equal(
    jianpuTextState.preserveEditedJianpuText(edited, generated, true, baseline),
    `USER|${correctedMiddle}|TAIL`,
  )
})

test('marker correction keeps canonical page text as the merge base', () => {
  const correctionStart = convertViewSource.indexOf('async function applyCorrections')
  const correctionEnd = convertViewSource.indexOf('function transposeOctaveShift', correctionStart)
  const correctionHandler = convertViewSource.slice(correctionStart, correctionEnd)

  assert.match(correctionHandler, /preserveEditedJianpuText\([\s\S]*page\.textAnchorBaselineText/)
  assert.match(correctionHandler, /jianpuText:\s*nextPageText/)
  assert.match(correctionHandler, /replaceJianpuSectionBody\([\s\S]*nextPageText/)
})

test('source selection scrolls a target note into the horizontal viewport', () => {
  assert.equal(
    editorViewport.horizontalScrollIntoView({
      scrollLeft: 0,
      clientWidth: 120,
      paddingLeft: 10,
      charWidth: 8,
      startColumn: 24,
      endColumn: 25,
    }),
    106,
  )
  assert.equal(
    editorViewport.horizontalScrollIntoView({
      scrollLeft: 160,
      clientWidth: 120,
      paddingLeft: 10,
      charWidth: 8,
      startColumn: 4,
      endColumn: 5,
    }),
    26,
  )
  assert.match(jianpuEditorSource, /nextTick\(\(\) => scrollRangeIntoView\(element, start, end\)\)/)
  assert.match(jianpuEditorSource, /horizontalScrollIntoView\(/)
})

test('original preview hit targets stay scoped to the displayed source-map sheet', () => {
  assert.match(
    originalPreviewSource,
    /sourceSheet\.value\?\.elements\.filter\(/,
  )
  assert.doesNotMatch(originalPreviewSource, /sheets\.flatMap\(/)
})

test('editable SVG preview renders no embedded static OCR', () => {
  assert.doesNotMatch(svgPreviewSource, /hide-static-ocr/)
  assert.doesNotMatch(svgPreviewSource, /shouldHideStaticOcr/)
  assert.doesNotMatch(
    svgPreviewSource,
    /props\.editableOcr\s*&&\s*ocrBlocks\.value\.length/,
  )
})

test('recognition dashboard keeps a stable first-row height across window states', () => {
  assert.match(
    recognizeViewSource,
    /grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)/,
  )
  assert.match(
    recognizeViewSource,
    /\.card-recognition,\s*\.card-stats\s*\{[^}]*min-height:\s*280px/s,
  )
  assert.match(
    recognizeViewSource,
    /@media \(max-height:\s*840px\)[\s\S]*?\.card-recognition,\s*\.card-stats\s*\{[^}]*min-height:\s*260px/s,
  )
  assert.doesNotMatch(recognizeViewSource, /minmax\((?:280|260)px,\s*auto\)/)
  assert.match(
    recognizeViewSource,
    /\.card-title\s*\{[^}]*flex-shrink:\s*0/s,
  )
  assert.match(
    recognizeViewSource,
    /\.card-stats-scroll\s*\{[^}]*min-height:\s*0/s,
  )
  assert.match(
    historyQuickEntrySource,
    /\.history-quick\s*\{[^}]*min-height:\s*0[^}]*overflow-y:\s*auto/s,
  )
})

test('recognition controls stay inside the card while progress is visible', () => {
  assert.doesNotMatch(recognizeViewSource, /card-recognition--compact/)
  assert.match(
    recognizeViewSource,
    /'dashboard-grid--busy':\s*store\.activePageTaskCount/,
  )
  assert.match(
    recognizeViewSource,
    /\.dashboard-grid--busy\s*\{[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)/s,
  )
  assert.match(
    recognizeViewSource,
    /@media \(max-height:\s*840px\)[\s\S]*?\.dashboard-grid--busy\s*\{[^}]*grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)/s,
  )
  assert.match(
    recognizeViewSource,
    /\.card-recognition \.card-footer\s*\{[^}]*flex-wrap:\s*nowrap/s,
  )
})

test('efficiency dashboard shows a date label for every day', () => {
  assert.doesNotMatch(efficiencyDashboardSource, /v-if="day\.showLabel"/)
  assert.doesNotMatch(efficiencyDashboardSource, /i\s*%\s*2/)
  assert.match(
    efficiencyDashboardSource,
    /shortLabel:\s*`\$\{d\.getMonth\(\) \+ 1\}\/\$\{d\.getDate\(\)\}`/,
  )
})

test('history preview support is defined in one place', () => {
  assert.equal(historyPageState.isPreviewableHistoryFile('score.PDF'), true)
  assert.equal(historyPageState.isPreviewableHistoryFile('score.musicxml'), false)
})

test('batch render requests preserve page-local source metadata', () => {
  const pages = [
    {
      inputFileName: 'p1.png',
      inputFileId: 'input-1',
      originalFileId: 'original-1',
      musicxmlFileId: 'xml-1',
      jianpuText: '1 2 |',
      ocrText: '文字一',
    },
    {
      inputFileName: 'p2.png',
      inputFileId: 'input-2',
      originalFileId: '',
      musicxmlFileId: 'xml-2',
      jianpuText: '3 4 |',
      ocrText: '',
    },
  ]
  const text = utils.composeJianpuPageText(pages)
  const requests = batchRender.buildBatchRenderRequests(pages, {
    jianpuText: text,
    title: '简谱',
  })

  assert.equal(requests.length, 2)
  assert.equal(requests[0].page_image_file_id, 'original-1')
  assert.equal(requests[0].ocr_text, '文字一')
  assert.equal(requests[1].page_image_file_id, 'input-2')
  assert.equal(requests[1].jianpu_text, '3 4 |')
})

test('sparse batch render requests preserve original source page index and anchors', () => {
  const pages = Array.from({ length: 6 }, (_, index) => ({
    inputFileName: `p${index + 1}.png`,
    inputFileId: `input-${index + 1}`,
    originalFileId: `original-${index + 1}`,
    musicxmlFileId: index === 3 ? 'xml-4' : '',
    jianpuText: index === 3 ? '1 2 |' : '',
    ocrText: '',
    textAnchors: index === 3 ? [{ source_id: 's1:i10' }] : [],
  }))
  const text = utils.composeJianpuPageText(pages)
  const requests = batchRender.buildBatchRenderRequests(pages, {
    jianpuText: text,
    title: '简谱',
  })

  assert.equal(requests.length, 1)
  assert.equal(requests[0].source_page_index, 3)
  assert.deepEqual(requests[0].text_anchors, [{ source_id: 's1:i10' }])
})

test('combined batch render keeps source pages separate', () => {
  const pages = [
    {
      inputFileName: 'p1.png',
      inputFileId: 'input-1',
      originalFileId: '',
      musicxmlFileId: 'xml-1',
      jianpuText: '1 |',
      ocrText: '',
    },
  ]

  assert.deepEqual(
    batchRender.buildBatchRenderRequests(pages, {
      jianpuText: '1 |\n2 |',
      title: '简谱',
      combineJianpuText: true,
    }),
    [{
      jianpu_text: '1 |\n2 |',
      include_ocr_text: false,
      title: '简谱',
    }],
  )
  assert.equal(batchRender.buildSourcePageRenderRequests(pages, '简谱').length, 1)
})

test('render response helpers normalize fallback ids and OCR text', () => {
  const pages = [
    { svg_file_id: 'svg-1', page_index: 0, page_width: 1, page_height: 1 },
  ]

  assert.deepEqual(batchRender.renderResponsePageIds(pages, 'fallback'), ['svg-1'])
  assert.deepEqual(batchRender.renderResponsePageIds([], 'fallback'), ['fallback'])
  assert.deepEqual(
    batchRender.renderResponsePageOcrTexts(pages),
    [{ page_index: 0, ocr_text: '' }],
  )
})

test('OCR text roundtrip preserves semantic attachment metadata', () => {
  const payload = JSON.stringify([{
    id: 'p0|ocr-1',
    text: '提示',
    bbox: [100, 200, 180, 228],
    role: 'expression',
    fontSize: 20,
    sourcePageIndex: 0,
    sourceAttachmentId: 'ocr-1',
    anchor: {
      kind: 'source_element',
      source_id: 's1:i9',
      offset_x: 12,
      offset_y: -4,
    },
  }])

  const blocks = ocrText.parseOcrText(payload)
  const roundtrip = ocrText.parseOcrText(ocrText.serializeOcrText(blocks))

  assert.equal(roundtrip[0].sourcePageIndex, 0)
  assert.equal(roundtrip[0].sourceAttachmentId, 'ocr-1')
  assert.equal(roundtrip[0].anchor.source_id, 's1:i9')
  assert.equal(roundtrip[0].anchor.offset_x, 12)
})

test('API wrappers return an error tuple instead of rejecting', async () => {
  const previousWindow = globalThis.window
  const previousFetch = globalThis.fetch
  let authorization = ''
  globalThis.window = {
    api: {
      getBackendConnection: async () => ({
        baseURL: 'http://test.invalid',
        token: 'process-local-test-token',
      }),
    },
  }
  globalThis.fetch = async (_input, options) => {
    authorization = new Headers(options?.headers).get('authorization') ?? ''
    throw new Error('network down')
  }

  try {
    await apiClient.initializeBackendConnection()
    const result = await apiClient.apiFetch('/health')

    assert.equal(result.data, null)
    assert.equal(result.error?.message, 'network down')
    assert.equal(authorization, 'Bearer process-local-test-token')
    await assert.rejects(apiClient.requireData(Promise.resolve(result)), /network down/)
  } finally {
    globalThis.window = previousWindow
    globalThis.fetch = previousFetch
  }
})

// ---------------------------------------------------------------------------
// 小节编号金样例：与 tests/test_jianpu_measure_numbering.py 使用完全相同的样例文本。
// 任一侧语义变化时，对应测试应先变红；改动一侧必须同步另一侧。
// 计数真值 = 后端 parse_jianpu_score 的 flush 结果（每小节占 repeat_count 个号）。
// ---------------------------------------------------------------------------

const GOLDEN_HEADER = '1=C\n4/4\n'

function goldenLabels(body) {
  return utils.jianpuGutterLabels(GOLDEN_HEADER + body).filter(Boolean)
}

test('一行内多个小节按小节线计数并显示区间', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 | 2 3 4 5 |'), ['1-2'])
  assert.deepEqual(goldenLabels('1 2 3 4 | 2 3 4 5 | 3 4 5 6 |'), ['1-3'])
  // 后续行号不再漂移。
  assert.deepEqual(goldenLabels('1 2 3 4 | 2 3 4 5 |\n1 2 3 4 |'), ['1-2', '3'])
})

test('区间标签尊重起始小节号偏移', () => {
  assert.deepEqual(
    utils.jianpuGutterLabels(GOLDEN_HEADER + '1 2 3 4 | 2 3 4 5 |', 5).filter(Boolean),
    ['5-6'],
  )
})

test('前向反复占多个号，区间随反复数扩张', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 *3 |'), ['1-3'])
  assert.deepEqual(goldenLabels('1 2 3 4 *3 |\n1 2 3 4 |'), ['1-3', '4'])
})

test('后向反复占多个号', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 | *3'), ['1-3'])
  assert.deepEqual(goldenLabels('1 2 3 4 | *3\n1 2 3 4 |'), ['1-3', '4'])
})

test('backward 反复覆盖上一小节的反复次数而非叠加', () => {
  assert.deepEqual(goldenLabels('1 2 *2 | *3'), ['1-3'])
})

test('反复结构中 |: 与 :| 不产生空小节', () => {
  assert.deepEqual(goldenLabels('|: 1 2 3 4 :|'), ['1'])
  // :| 之后紧跟的空小节被吞掉。
  assert.deepEqual(goldenLabels('|: 1 2 3 4 :| | 5 6 7 1 |'), ['1-2'])
})

test('backward 反复之后的空小节被吞掉', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 :| *2 |'), ['1-2'])
  assert.deepEqual(goldenLabels('1 2 3 4 :| *2 |\n1 2 3 4 |'), ['1-2', '3'])
})

test('非 :|/*N 之后的孤立小节线占一个号（整小节休止）', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 |\n|\n5 6 7 1 |'), ['1', '2', '3'])
})

test('末小节可以没有小节线，标签挂在最后内容行', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 |\n5 6 7 1'), ['1', '2'])
  assert.deepEqual(
    utils.jianpuPageSummaries(GOLDEN_HEADER + '1 2 3 4 |\n5 6 7 1').map((p) => [
      p.firstMeasureNumber,
      p.lastMeasureNumber,
    ]),
    [[1, 2]],
  )
})

test('小节跨行时换行不产生新小节', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 |\n5 6\n7 1 |'), ['1', '2'])
})

test('行首 AI 小节号标签被剥离', () => {
  assert.deepEqual(goldenLabels('272: 1 2 3 4 |'), ['1'])
})

test('行内注释里的小节线不计数', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 | // 注释 | 不应计数\n5 6 7 1 |'), ['1', '2'])
})

test('行内容错 tempo 不吞掉所在行的小节', () => {
  assert.deepEqual(goldenLabels('1 2 3 4 |\ntempo=80 5 6 7 1 |'), ['1', '2'])
})

test('跳房子是结构标注不占小节号，:| 之后 {N.} | 的空小节被吞掉', () => {
  // 与 tests/test_jianpu_measure_numbering.py 的房子样例一一对应。
  assert.deepEqual(
    goldenLabels('|: 1 2 3 4 | {1.} 5 6 5 4 :| {2.} 7 1\' 2\' 1\' |'),
    ['1-3'],
  )
  assert.deepEqual(
    goldenLabels('|: 1 2 3 4 | {1.} 5 6 5 4 :| {2.} | 7 1\' 2\' 1\' |'),
    ['1-3'],
  )
  // 非 :| 之后的 `{1.} |` 仍按空小节保留为整小节休止，占 1 个号。
  assert.deepEqual(goldenLabels('{1.} | 1 2 3 4 |'), ['1-2'])
})

test('分页分谱：各声部从本页起始号并行编号，页跨度取最大值', () => {
  const text = [
    '// @page 1',
    '// @part 1 name="A"',
    '1 2 3 4 |',
    '1 2 3 4 | 5 6 7 1 |',
    '// @part 2 name="B"',
    '3 4 5 6 |',
    '1 1 1 1 |',
    '// @page 2',
    '// @part 1 name="A"',
    '2 2 2 2 |',
    '// @part 2 name="B"',
    '3 3 3 3 |',
  ].join('\n')

  assert.deepEqual(utils.jianpuGutterLabels(text), [
    'P1', '', '1', '2-3', '', '1', '2', 'P2', '', '4', '', '4',
  ])
  assert.deepEqual(
    utils.jianpuPageSummaries(text).map((p) => [
      p.firstMeasureNumber,
      p.lastMeasureNumber,
      p.measureCount,
    ]),
    [[1, 3, 3], [4, 4, 1]],
  )
})

test('超长区间标签截断为 n+', () => {
  const line = '1 | '.repeat(64).trim()
  assert.deepEqual(
    utils.jianpuGutterLabels(GOLDEN_HEADER + line, 1000).filter(Boolean),
    ['1000+'],
  )
  // 3 字符区间不截断；4 字符区间（如 "10-1"）截断。
  assert.deepEqual(
    utils.jianpuGutterLabels(GOLDEN_HEADER + '1 2 3 4 | 2 3 4 5 |', 100).filter(Boolean),
    ['100+'],
  )
  assert.deepEqual(
    utils.jianpuGutterLabels(GOLDEN_HEADER + '1 2 3 4 | 2 3 4 5 |', 9).filter(Boolean),
    ['9-10'],
  )
})

test('multi-line lyric blocks do not advance measure numbers and mask cleanly', async () => {
  const text = '1 2 3 4 | 5 6 7 1 |\n/L: 一 二 三 四 |\n五 六 七 一/\n'

  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-2', '1', '2', ''])
  assert.equal(utils.jianpuMeasureCount(text), 2)

  const syntax = await import(syntaxModuleUrl)
  assert.deepEqual([...syntax.lyricBlockLineIndexes(text)], [1, 2])
  const masked = syntax.maskJianpuLyricBlocks(text)
  assert.equal(masked.split('\n').length, text.split('\n').length)
  assert.ok(!masked.includes('一') && !masked.includes('五'))
})

test('lyric gutter labels follow per-line covered measure ranges', () => {
  // 用户示例：歌词第 1 行覆盖 3 小节，后续行各 1 小节。
  const text = '1 | 2 | 3 | 4 | 5 |\n/L: a b | c d | e |\nf |\ng/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-5', '1-3', '4', '5', ''])
})

test('lyric gutter labels use repeat-weighted display numbers like the body', () => {
  // 前向反复：小节 1 占 2 个号（1-2），小节 2 占 3 个号（3-5）。
  const text = '1 2 3 4 *2 | 5 6 7 1 *3 |\n/L: a b | c d/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-5', '1-5', ''])
})

test('lyric gutter labels let content lines join their open measure', () => {
  // 跨行小节：内容行与闭合行都计入该小节。
  const text = '1 | 2 | 3 |\n/L: a | b\nc | d/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-3', '1-2', '2-3', ''])
})

test('lyric gutter labels cover lines without any bar separator', () => {
  // 整段歌词不写 `|`：每个内容行都显示当前小节号；`/L:` 前缀行与
  // 结束符独占行无内容，不显示标签。
  const text = '1 | 2 | 3 |\n/L:\n春 眠\n处处闻啼鸟\n/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['1-3', '', '1', '1', '', ''])
})

test('lyric gutter labels ignore & lanes and count empty measures', () => {
  assert.deepEqual(
    utils.jianpuGutterLabels('1 | 2 |\n/L: a & b | c & d/\n'),
    ['1-2', '1-2', ''],
  )
  assert.deepEqual(
    utils.jianpuGutterLabels('1 | 2 | 3 |\n/L: a || b/\n'),
    ['1-3', '1-3', ''],
  )
})

test('lyric gutter labels handle truncated and overflowing lyrics gracefully', () => {
  // 截断：歌词只覆盖前 2 个小节。
  assert.deepEqual(
    utils.jianpuGutterLabels('1 | 2 | 3 | 4 | 5 |\n/L: a | b/\n'),
    ['1-5', '1-2', ''],
  )
  // 溢出（非法文档）：超出谱面的小节行不显示标签，不崩溃。
  assert.deepEqual(
    utils.jianpuGutterLabels('1 |\n/L: a | b\nc/\n'),
    ['1', '1', '', ''],
  )
  // 未闭合块（非法文档）：尽力扫描到文末。
  assert.deepEqual(
    utils.jianpuGutterLabels('1 | 2 |\n/L: a | b\n'),
    ['1-2', '1-2', ''],
  )
})

test('lyric gutter labels respect the initial measure number', () => {
  assert.deepEqual(
    utils.jianpuGutterLabels('1 | 2 |\n/L: a | b/\n', 5),
    ['5-6', '5-6', ''],
  )
})

test('lyric gutter labels work in documents with explicit part markers', () => {
  // @part 标记行会触发空 finishPart，不能影响 measureSpans 的首声部收集。
  const text = '// @page 1 name="p1.png"\n// @part 1 name="Voice"\ntempo=120\n1=C\n2/4\nq5 q6 q7 |\nq5 q6 q7 |\n\n/L:1 2 3|\n 3 5 4|\n/\n'
  assert.deepEqual(utils.jianpuGutterLabels(text), ['P1', '', '', '', '', '1', '2', '', '1', '2', '', ''])
})

test('lyric gutter labels match across multi-part documents', () => {
  const single = '1 | 2 |\n/L: a | b/\n'
  const multi = '// @part 1 name="a"\n1 | 2 |\n// @part 2 name="b"\n3 | 4 |\n/L: a | b/\n'
  assert.deepEqual(utils.jianpuGutterLabels(single), ['1-2', '1-2', ''])
  assert.deepEqual(
    utils.jianpuGutterLabels(multi),
    ['', '1-2', '', '1-2', '1-2', ''],
  )
})

test('lyric block range skips // comment markers when unterminated', async () => {
  const syntax = await import(syntaxModuleUrl)
  const unterminated = syntax.findLyricBlockRange('1 2 |\n/L: 一 二\n// 注释\n')
  assert.ok(unterminated.end < unterminated.start)
  const terminated = syntax.findLyricBlockRange('1 2 |\n/L: 一 二 |\n三 四/\n')
  assert.equal('1 2 |\n/L: 一 二 |\n三 四/\n'[terminated.end], '/')
})
