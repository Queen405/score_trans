import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { compileScript, parse } from 'vue/compiler-sfc'

const require = createRequire(import.meta.url)
const { createRenderer, h, nextTick, reactive, ref, watch } = require('vue')
const { createPinia, setActivePinia } = require('pinia')
const root = fileURLToPath(new URL('../src/renderer/src/', import.meta.url))
const before = '1=C\n4/4\n1 2 3 4 |'
const edited = '1=D\n4/4\n1 2 3 4 |'
const transposed = "1=D\n4/4\n7, #1 2 3 |"
const success = { data: { transposed_text: transposed }, error: null }

// Compile the real modules and SFC setup; replace only environment/API boundaries.
function createLoader(overrides) {
  const cache = new Map()
  return function load(relative) {
    const filename = path.resolve(root, relative)
    if (overrides[filename]) return overrides[filename]
    if (cache.has(filename)) return cache.get(filename)
    const text = fs.readFileSync(filename, 'utf8')
    const source = filename.endsWith('.vue')
      ? compileScript(parse(text, { filename }).descriptor, { id: filename }).content
      : text
    const compiled = ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
      fileName: filename,
    }).outputText
    const module = { exports: {} }
    cache.set(filename, module.exports)
    const localRequire = (specifier) => {
      if (overrides[specifier]) return overrides[specifier]
      if (!specifier.startsWith('.')) return require(specifier)
      const resolved = path.resolve(path.dirname(filename), specifier)
      if (path.extname(resolved)) return load(resolved)
      if (fs.existsSync(`${resolved}.ts`)) return load(`${resolved}.ts`)
      return load(path.join(resolved, 'index.ts'))
    }
    new Function('require', 'module', 'exports', compiled)(localRequire, module, module.exports)
    return module.exports
  }
}

const renderer = createRenderer({
  createComment: () => ({}),
  insert() {},
  remove() {},
  parentNode: () => null,
  nextSibling: () => null,
})

function deferred() {
  let resolve
  const promise = new Promise((done) => { resolve = done })
  return { promise, resolve }
}

async function settle() {
  await new Promise((resolve) => setImmediate(resolve))
  await nextTick()
}

function convertPreflight(bindings) {
  const source = parse(fs.readFileSync(path.join(root, 'views/ConvertView.vue'), 'utf8')).descriptor.scriptSetup.content
  const ast = ts.createSourceFile('ConvertView.ts', source, ts.ScriptTarget.Latest, true)
  const names = new Set(['flushPendingEdits', 'persistUnsavedBeforeReplace', 'actionLabel'])
  const declarations = ast.statements
    .filter((node) => ts.isFunctionDeclaration(node) && names.has(node.name.text))
    .map((node) => node.getText(ast)).join('\n')
  assert.equal(declarations.includes('persistUnsavedBeforeReplace'), true)
  const compiled = ts.transpileModule(declarations, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  return new Function(...Object.keys(bindings), `${compiled}\nreturn persistUnsavedBeforeReplace;`)(...Object.values(bindings))
}

function setup(t, entrypoint = 'quick', { enabled = true } = {}) {
  const requests = []
  const saved = []
  const events = []
  const errors = []
  const pending = deferred()
  const settings = reactive({ jianpuAutoTranspose: enabled, jianpuLayoutKey: 'layout' })
  const message = { error: (value) => errors.push(value), warning() {}, success() {} }
  const log = { addError() {}, addLog() {} }
  const historyApi = {
    async saveBatch(id, request) {
      events.push('save')
      saved.push(JSON.parse(JSON.stringify(request)))
      return {
        data: { ...request, id, pages: request.pages.map((page) => ({ ...page, id: page.page_id })) },
        error: null,
      }
    },
    async get() {
      events.push('get')
      return {
        data: {
          id: 20, pages: [{ id: 200, input_file_name: 'target.png', input_file_id: '', jianpu_text: before }],
          jianpu_text: before, render_page_file_ids: ['rendered'], render_layout_key: 'layout',
          engine_version: load('utils/jianpuLayout.ts').PUBLICATION_ENGINE_VERSION,
        },
        error: null,
      }
    },
  }
  const mocks = {
    'naive-ui': { useMessage: () => message },
    [path.join(root, 'stores/settings.ts')]: { useSettingsStore: () => settings },
    [path.join(root, 'stores/log.ts')]: { useLogStore: () => log },
    [path.join(root, 'api/jianpu.ts')]: { jianpuApi: { rekeyText: async (request) => {
      requests.push(request)
      return pending.promise
    } } },
    [path.join(root, 'api/history.ts')]: { historyApi },
    [path.join(root, 'api/client.ts')]: {
      ApiError: class ApiError extends Error {},
      requireData: async (promise) => {
        const result = await promise
        if (result.error) throw result.error
        return result.data
      },
    },
    [path.join(root, 'api/files.ts')]: { filesApi: { existsMany: async () => ({ data: { rendered: true }, error: null }) } },
    [path.join(root, 'utils/historyEvents.ts')]: { notifyHistoryUpdated() {} },
    [path.join(root, 'composables/usePublicationRender.ts')]: { usePublicationRender: () => ({}) },
    [path.join(root, 'composables/useViewPersistence.ts')]: { loadEditorScroll: () => null, saveEditorScroll() {} },
  }
  const load = createLoader(mocks)
  setActivePinia(createPinia())
  const store = load('stores/workspace.ts').useWorkspaceStore()
  store.loadBatch([{ inputFileName: 'current.png', inputFileId: '', historyBatchId: 10, historyPageId: 100, jianpuText: before }], 0, [], before)
  const originalBatchId = store.currentBatchId
  const model = ref(before)
  const stopWatch = watch(model, (text) => store.setBatchJianpuText(text, true))
  const Editor = load('components/JianpuEditor.vue').default
  Editor.render = () => null
  const editorRef = ref(null)
  const app = renderer.createApp({ render: () => h(Editor, {
    ref: editorRef,
    modelValue: model.value,
    'onUpdate:modelValue': (text) => { model.value = text },
  }) })
  app.mount({})
  const editor = editorRef.value
  t.after(() => { stopWatch(); app.unmount() })
  const flushPendingEdits = async () => {
    events.push('flush')
    await editor.flushPendingAutoTranspose()
  }
  let restore
  if (entrypoint === 'quick') {
    const { useHistoryRestore } = load('composables/useHistoryRestore.ts')
    restore = () => useHistoryRestore(flushPendingEdits).restoreBatch({ id: 20 })
  } else {
    const persist = convertPreflight({
      store, log, message, jianpuEditorRef: { value: { flushPendingAutoTranspose: flushPendingEdits } },
      workspacePersistence: load('utils/workspacePersistence.ts').createWorkspacePersistence(historyApi),
      isRenderAborted: () => false,
      t: load('i18n/index.ts').t,
    })
    restore = () => persist('restore')
  }
  return {
    store, model, editor, settings, requests, saved, events, errors, pending, originalBatchId,
    historyApi, rekeyApi: mocks[path.join(root, 'api/jianpu.ts')].jianpuApi, restore,
    async edit(text = edited) {
      const old = model.value
      model.value = text
      editor.$.setupState.scheduleKeyChangeCheck(old, text)
      await nextTick()
    },
  }
}

for (const entrypoint of ['quick', 'convert']) {
  test(`${entrypoint}: restore saves transposed notes when called during debounce`, async (t) => {
    const ctx = setup(t, entrypoint)
    await ctx.edit()
    const restoring = ctx.restore()
    await settle()
    assert.equal(ctx.requests.length, 1)
    assert.equal(ctx.saved.length, 0, 'must not save before the transpose response')
    assert.equal(ctx.store.currentBatchId, ctx.originalBatchId)
    ctx.pending.resolve(success)
    assert.equal(await restoring, true)
    assert.equal(ctx.saved[0].jianpu_text, transposed)
    assert.deepEqual(ctx.requests[0], { text: edited, previous_text: before })
    assert.equal(ctx.store.isBusy, false)
    if (entrypoint === 'quick') assert.deepEqual(ctx.events, ['flush', 'save', 'get'])
  })

  test(`${entrypoint}: restore waits for an in-flight transpose without a second request`, async (t) => {
    t.mock.timers.enable({ apis: ['setTimeout'] })
    const ctx = setup(t, entrypoint)
    await ctx.edit()
    t.mock.timers.tick(600)
    assert.equal(ctx.requests.length, 1)
    const restoring = ctx.restore()
    await settle()
    assert.equal(ctx.saved.length, 0)
    ctx.pending.resolve(success)
    assert.equal(await restoring, true)
    assert.equal(ctx.requests.length, 1)
    assert.equal(ctx.saved[0].jianpu_text, transposed)
  })

  test(`${entrypoint}: flush runs before the dirty check`, async (t) => {
    const ctx = setup(t, entrypoint)
    await ctx.edit()
    ctx.store.acknowledgeBatchChanges(ctx.store.captureBatchChangeRevision(ctx.originalBatchId), undefined, ctx.originalBatchId)
    assert.equal(ctx.store.hasUnsavedChanges, false)
    const restoring = ctx.restore()
    await settle()
    assert.equal(ctx.requests.length, 1)
    ctx.pending.resolve(success)
    assert.equal(await restoring, true)
    assert.equal(ctx.saved[0].jianpu_text, transposed)
  })

  for (const result of [
    { data: null, error: new Error('offline') },
    { data: { skip_reason: 'parse_error' }, error: null },
    { data: { transposed_text: '' }, error: null },
  ]) {
    test(`${entrypoint}: failed or skipped transpose cancels restore (${result.error?.message ?? result.data.skip_reason ?? 'empty result'})`, async (t) => {
      const ctx = setup(t, entrypoint)
      await ctx.edit()
      const restoring = ctx.restore()
      ctx.pending.resolve(result)
      assert.equal(await restoring, false)
      assert.equal(ctx.saved.length, 0)
      assert.equal(ctx.events.includes('get'), false)
      assert.equal(ctx.store.currentBatchId, ctx.originalBatchId)
      assert.equal(ctx.store.currentBatchJianpuText, edited)
      assert.equal(ctx.store.hasUnsavedChanges, true)
      assert.equal(ctx.store.isBusy, false)
      assert.equal(ctx.errors.length, 1)
      assert.equal(await ctx.restore(), false, 'a second restore must not silently save the failed edit')
      assert.equal(ctx.saved.length, 0)
    })
  }

  test(`${entrypoint}: a save failure keeps the transposed current batch`, async (t) => {
    const ctx = setup(t, entrypoint)
    ctx.historyApi.saveBatch = async () => ({ data: null, error: new Error('save failed') })
    await ctx.edit()
    const restoring = ctx.restore()
    ctx.pending.resolve(success)
    assert.equal(await restoring, false)
    assert.equal(ctx.store.currentBatchId, ctx.originalBatchId)
    assert.equal(ctx.store.currentBatchJianpuText, transposed)
    assert.equal(ctx.store.hasUnsavedChanges, true)
    assert.equal(ctx.store.isBusy, false)
  })

  test(`${entrypoint}: restore without pending edits does not transpose or save`, async (t) => {
    const ctx = setup(t, entrypoint)
    assert.equal(await ctx.restore(), true)
    assert.equal(ctx.requests.length, 0)
    assert.equal(ctx.saved.length, 0)
    assert.equal(ctx.store.isBusy, false)
  })

  test(`${entrypoint}: disabled auto-transpose preserves explicitly edited notes`, async (t) => {
    const ctx = setup(t, entrypoint, { enabled: false })
    await ctx.edit()
    assert.equal(await ctx.restore(), true)
    assert.equal(ctx.requests.length, 0)
    assert.equal(ctx.saved[0].jianpu_text, edited)
  })

  for (const emptyState of ['no selected batch', 'removed final page']) {
    test(`${entrypoint}: ${emptyState} edits do not block history replacement`, async (t) => {
      const ctx = setup(t, entrypoint, { enabled: false })
      if (emptyState === 'no selected batch') ctx.store.reset()
      else ctx.store.removePage(0)
      await ctx.edit('1 2 3 |')

      assert.equal(ctx.store.currentBatchId, null)
      assert.equal(ctx.store.hasUnsavedChanges, true)
      assert.equal(await ctx.restore(), true)
      assert.equal(ctx.saved.length, 0)
      assert.equal(ctx.errors.length, 0)
      if (entrypoint === 'quick') {
        assert.notEqual(ctx.store.currentBatchId, ctx.originalBatchId)
        assert.equal(ctx.store.hasUnsavedChanges, false)
      }
    })
  }

  for (const deletion of ['single deletion', 'delete-all']) {
    test(`${entrypoint}: ${deletion} of the source batch does not block replacement`, async (t) => {
      const ctx = setup(t, entrypoint, { enabled: false })
      ctx.historyApi.saveBatch = async () => ({
        data: null,
        error: Object.assign(new Error('Batch not found'), { status: 404 }),
      })
      await ctx.edit()

      assert.equal(await ctx.restore(), true)
      assert.equal(ctx.store.isBusy, false)
      assert.equal(ctx.errors.length, 0)
      if (entrypoint === 'quick') {
        assert.notEqual(ctx.store.currentBatchId, ctx.originalBatchId)
        assert.equal(ctx.store.hasUnsavedChanges, false)
      }
    })
  }
}

test('a missing restore target keeps edits from an already deleted source batch', async (t) => {
  const ctx = setup(t, 'quick', { enabled: false })
  ctx.historyApi.saveBatch = async () => ({
    data: null,
    error: Object.assign(new Error('Batch not found'), { status: 404 }),
  })
  ctx.historyApi.get = async () => {
    ctx.events.push('get')
    return {
      data: null,
      error: Object.assign(new Error('Batch not found'), { status: 404 }),
    }
  }
  await ctx.edit()

  assert.equal(await ctx.restore(), false)
  assert.equal(ctx.events.includes('get'), true)
  assert.equal(ctx.store.currentBatchId, ctx.originalBatchId)
  assert.equal(ctx.store.currentBatchJianpuText, edited)
  assert.equal(ctx.store.hasUnsavedChanges, true)
  assert.equal(ctx.errors.length, 1)
})

test('a stale transpose response cannot authorize history replacement', async (t) => {
  const ctx = setup(t)
  await ctx.edit()
  const restoring = ctx.restore()
  await settle()
  assert.equal(ctx.requests.length, 1)
  ctx.model.value = '1=G\n4/4\n1 2 3 4 |'
  await nextTick()
  ctx.pending.resolve(success)
  assert.equal(await restoring, false)
  assert.equal(ctx.saved.length, 0)
  assert.equal(ctx.store.currentBatchId, ctx.originalBatchId)
})

test('a successful unchanged transpose is safe to save', async (t) => {
  const ctx = setup(t)
  await ctx.edit()
  const restoring = ctx.restore()
  ctx.pending.resolve({ data: { transposed_text: edited }, error: null })
  assert.equal(await restoring, true)
  assert.equal(ctx.saved[0].jianpu_text, edited)
})

test('a rejected background request is handled and a restore can retry its original baseline', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const ctx = setup(t)
  ctx.rekeyApi.rekeyText = async () => { throw new Error('offline') }
  await ctx.edit()
  t.mock.timers.tick(600)
  await settle()
  assert.equal(ctx.editor.transposing, false)
  assert.equal(ctx.store.hasUnsavedChanges, true)
  ctx.rekeyApi.rekeyText = async (request) => {
    ctx.requests.push(request)
    return success
  }
  assert.equal(await ctx.restore(), true)
  assert.deepEqual(ctx.requests, [{ text: edited, previous_text: before }])
  assert.equal(ctx.saved[0].jianpu_text, transposed)
})

test('disabling auto-transpose invalidates an in-flight result without blocking later manual saves', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const ctx = setup(t)
  await ctx.edit()
  t.mock.timers.tick(600)
  ctx.settings.jianpuAutoTranspose = false
  await nextTick()
  ctx.pending.resolve(success)
  await settle()
  assert.equal(ctx.model.value, edited)
  assert.equal(await ctx.restore(), true)
  assert.equal(ctx.saved[0].jianpu_text, edited)
})

// Exercise snapshot navigation with the real restore/confirmation functions and
// editor watchers, so an external editor sync cannot silently re-dirty the store.
function setupSnapshotNavigation(t) {
  const { computed, effectScope } = require('vue')
  const load = createLoader({ 'naive-ui': { useMessage: () => {}, enUS: {}, zhCN: {}, dateEnUS: {}, dateZhCN: {} } })
  setActivePinia(createPinia())
  const store = load('stores/workspace.ts').useWorkspaceStore()
  store.loadBatch([{
    inputFileName: 'score.png', inputFileId: '', historyBatchId: 10,
    historyPageId: 100, jianpuText: before,
  }], 0, ['rendered-A'], before)
  const jianpuText = ref(before)
  const discardConfirmVisible = ref(false)
  const finalSvgFileIds = ref(['rendered-A'])
  const requests = []
  const bindings = {
    store, jianpuText, discardConfirmVisible, ref, watch,
    discardConfirmAction: ref('恢复历史版本'),
    isViewingFinal: ref(true), snapshotHistoryOpen: ref(true),
    pendingRekeyApplied: ref(null), errorLine: ref(-1),
    operationalJianpuText: computed(() => jianpuText.value),
    syntaxStore: { schedule() {} },
    updateTextAnchorsAfterEdit() {}, updateTextAnchorsAfterRekey() {},
    setFinalSvgFileIds: (ids) => { finalSvgFileIds.value = ids },
    ...load('utils/jianpuPageSections.ts'),
    ...load('utils/textAnchorTracking.ts'),
    log: { addLog() {} }, message: { success() {} },
    historyApi: { saveBatch: (...args) => requests.push(args) },
    workspacePersistence: { saveBatch: (...args) => requests.push(args) },
    t: load('i18n/index.ts').t,
  }
  const source = parse(fs.readFileSync(path.join(root, 'views/ConvertView.vue'), 'utf8')).descriptor.scriptSetup.content
  const ast = ts.createSourceFile('ConvertView.ts', source, ts.ScriptTarget.Latest, true)
  const names = new Set([
    'restoreJianpuSnapshot', 'confirmDiscardUnsaved', 'settleDiscardConfirmation',
    'snapshotSourceLabel', 'formatSnapshotTime',
  ])
  const declarations = ast.statements.filter((node) => (
    ts.isFunctionDeclaration(node) && names.has(node.name.text)
  ) || (
    ts.isExpressionStatement(node)
    && (node.getText(ast).startsWith('watch(() => store.currentBatchJianpuText,')
      || node.getText(ast).startsWith('watch(jianpuText,'))
  )).map((node) => node.getText(ast)).join('\n')
  const compiled = ts.transpileModule(declarations, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  const scope = effectScope()
  t.after(() => scope.stop())
  const actions = scope.run(() => new Function(...Object.keys(bindings), `
    let discardConfirmResolver = null;
    let editorSyncGeneration = 0;
    let pendingExternalEditorSync = null;
    ${compiled}
    return { restoreJianpuSnapshot, settleDiscardConfirmation };
  `)(...Object.values(bindings)))
  return {
    store, jianpuText, discardConfirmVisible, finalSvgFileIds, requests,
    settle: actions.settleDiscardConfirmation,
    restore: (text) => actions.restoreJianpuSnapshot({
      jianpu_text: text, source: 'save', created_at: '2026-09-01 12:00:00',
    }),
  }
}

test('snapshots: A to B to A stays clean without confirmation or saves', async (t) => {
  const ctx = setupSnapshotNavigation(t)
  for (const text of [edited, before]) {
    await ctx.restore(text)
    await nextTick()
    assert.equal(ctx.jianpuText.value, text)
    assert.equal(ctx.store.currentBatchPages[0].jianpuText, text)
    assert.equal(ctx.store.currentBatchHasUnsavedChanges, false)
    assert.equal(ctx.store.currentBatchJianpuDirty, false)
    assert.equal(ctx.store.hasUnsavedChanges, false)
    assert.equal(ctx.discardConfirmVisible.value, false)
    assert.deepEqual(ctx.store.currentBatchRenderPageFileIds, [])
    assert.deepEqual(ctx.finalSvgFileIds.value, [])
  }
  assert.deepEqual(ctx.requests, [])
})

test('snapshots: real edits prompt; cancel retains them and discard restores cleanly', async (t) => {
  const ctx = setupSnapshotNavigation(t)
  await ctx.restore(edited)
  await nextTick()
  ctx.jianpuText.value = transposed
  await nextTick()
  assert.equal(ctx.store.currentBatchHasUnsavedChanges, true)

  const cancelled = ctx.restore(before)
  assert.equal(ctx.discardConfirmVisible.value, true)
  ctx.settle(false)
  await cancelled
  assert.equal(ctx.store.currentBatchJianpuText, transposed)
  assert.equal(ctx.store.currentBatchHasUnsavedChanges, true)

  const accepted = ctx.restore(before)
  assert.equal(ctx.discardConfirmVisible.value, true)
  ctx.settle(true)
  await accepted
  await nextTick()
  assert.equal(ctx.jianpuText.value, before)
  assert.equal(ctx.store.currentBatchHasUnsavedChanges, false)
  assert.equal(ctx.store.currentBatchPages[0].jianpuDirty, false)
  assert.deepEqual(ctx.requests, [])
})

test('snapshots: restoring only clears jianpu changes, preserving OCR and attachments', async (t) => {
  const ctx = setupSnapshotNavigation(t)
  ctx.store.setBatchJianpuText(transposed, true)
  ctx.store.setBatchRenderPageOcrText(0, 'edited OCR')
  ctx.store.markBatchAttachmentUserEdited()
  const restoring = ctx.restore(edited)
  ctx.settle(true)
  await restoring
  await nextTick()
  const id = ctx.store.currentBatchId
  assert.equal(ctx.store.isBatchChangeKindUnsaved(id, 'jianpu'), false)
  assert.equal(ctx.store.isBatchChangeKindUnsaved(id, 'ocr'), true)
  assert.equal(ctx.store.isBatchChangeKindUnsaved(id, 'attachments'), true)
  assert.equal(ctx.store.hasUnsavedChanges, true)
})

test('snapshots: navigation leaves another batch dirty', async (t) => {
  const ctx = setupSnapshotNavigation(t)
  const originalId = ctx.store.currentBatchId
  ctx.store.addInputPage('other.png', '')
  const otherId = ctx.store.currentBatchId
  assert.notEqual(otherId, originalId)
  ctx.store.setBatchJianpuText('5 6 |', true)
  ctx.store.selectBatch(originalId)
  await nextTick()
  await ctx.restore(edited)
  await nextTick()
  assert.equal(ctx.store.currentBatchHasUnsavedChanges, false)
  assert.equal(ctx.store.isBatchUnsaved(otherId), true)
  assert.equal(ctx.store.hasUnsavedChanges, true)
  assert.equal(ctx.store.batchJianpuTextFor(otherId), '5 6 |')
})
