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
const utilsModuleUrl = `data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`
const utils = await import(utilsModuleUrl)

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
}).outputText
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
const originalPreviewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/OriginalPreview.vue'),
  'utf8',
)
const svgPreviewSource = fs.readFileSync(
  path.resolve(here, '../src/renderer/src/components/SvgPreview.vue'),
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
    { startMeasureNumber: 1, jianpuText: firstPage },
    { jianpuText: secondPage },
  ])

  assert.deepEqual(
    utils.jianpuPageSummaries(text).map((summary) => [
      summary.startMeasureNumber,
      summary.endMeasureNumber,
      summary.measureCount,
    ]),
    [[1, 2, 2], [3, 4, 2]],
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

test('latest completed history state never opens a stale waiting picker', () => {
  const cachedStatus = 'waiting'
  const latestStatus = 'completed'

  assert.equal(cachedStatus, 'waiting')
  assert.equal(historyPageState.historyPageOpenAction(latestStatus), 'restore')
})

test('only the latest waiting history state opens the measure picker', () => {
  assert.equal(historyPageState.historyPageOpenAction('waiting'), 'choose')
  assert.equal(historyPageState.historyPageOpenAction('processing'), 'wait')
  assert.equal(historyPageState.historyPageOpenAction('pending'), 'wait')
  assert.equal(historyPageState.historyPageOpenAction('unrecognized'), 'restore')
  assert.equal(historyPageState.historyPageOpenAction('failed'), 'restore')
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
  const resetHandler = convertViewSource.match(
    /async function musicxmlToJianpu\(\): Promise<void> \{([\s\S]*?)\n\}/,
  )?.[1] ?? ''

  assert.match(resetHandler, /textAnchors:\s*result\.text_anchors\s*\?\?\s*\[\]/)
  assert.match(resetHandler, /textHash:\s*result\.text_hash\s*\?\?\s*''/)
})

test('original preview hit targets stay scoped to the displayed source-map sheet', () => {
  assert.match(
    originalPreviewSource,
    /sourceSheet\.value\?\.elements\.filter\(/,
  )
  assert.doesNotMatch(originalPreviewSource, /sheets\.flatMap\(/)
})

test('editable SVG preview always suppresses embedded static OCR', () => {
  assert.match(
    svgPreviewSource,
    /const shouldHideStaticOcr = computed\(\(\) => props\.editableOcr\)/,
  )
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

test('recognition controls stay inside the card while progress or waiting status is visible', () => {
  assert.doesNotMatch(recognizeViewSource, /card-recognition--compact/)
  assert.match(
    recognizeViewSource,
    /dashboard-grid--busy[\s\S]*store\.activePageTaskCount\s*\|\|\s*waitingPageCount/,
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

test('waiting measure messages roundtrip through history state', () => {
  const message = historyPageState.waitingMeasureMessage([8, 12, 16])

  assert.equal(message, '等待选择起始小节号：8、12、16')
  assert.deepEqual(historyPageState.parseWaitingMeasureOptions(message), [8, 12, 16])
  assert.equal(
    historyPageState.failedMeasureSelectionMessage([8, 12], '网络错误'),
    '等待选择起始小节号：8、12；选择小节号失败：网络错误',
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
      startMeasureNumber: 5,
    },
    {
      inputFileName: 'p2.png',
      inputFileId: 'input-2',
      originalFileId: '',
      musicxmlFileId: 'xml-2',
      jianpuText: '3 4 |',
      ocrText: '',
      startMeasureNumber: null,
    },
  ]
  const text = utils.composeJianpuPageText(pages)
  const requests = batchRender.buildBatchRenderRequests(pages, {
    jianpuText: text,
    title: '简谱',
  })

  assert.equal(requests.length, 2)
  assert.equal(requests[0].page_image_file_id, 'original-1')
  assert.equal(requests[0].start_measure_number, 5)
  assert.equal(requests[0].ocr_text, '文字一')
  assert.equal(requests[1].page_image_file_id, 'input-2')
  assert.equal(requests[1].jianpu_text, '3 4 |')
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
      startMeasureNumber: 9,
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
      start_measure_number: 9,
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
  globalThis.window = {
    api: {
      getBackendURL: () => 'http://test.invalid',
    },
  }
  globalThis.fetch = async () => {
    throw new Error('network down')
  }

  try {
    const result = await apiClient.apiFetch('/health')

    assert.equal(result.data, null)
    assert.equal(result.error?.message, 'network down')
    await assert.rejects(apiClient.requireData(Promise.resolve(result)), /network down/)
  } finally {
    globalThis.window = previousWindow
    globalThis.fetch = previousFetch
  }
})
