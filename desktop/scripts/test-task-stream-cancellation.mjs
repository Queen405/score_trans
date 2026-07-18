import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const here = path.dirname(fileURLToPath(import.meta.url))

function moduleUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
}

function compileTasks(clientUrl, eventStateUrl) {
  const sourcePath = path.resolve(here, '../src/renderer/src/api/tasks.ts')
  let compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  compiled = compiled.replace("from './client'", `from '${clientUrl}'`)
  compiled = compiled.replace("from '../utils/taskEventState'", `from '${eventStateUrl}'`)
  return moduleUrl(compiled)
}

function compileTypeScript(sourcePath) {
  const compiled = ts.transpileModule(fs.readFileSync(sourcePath, 'utf8'), {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: sourcePath,
  }).outputText
  return moduleUrl(compiled)
}

function nextTurn() {
  return new Promise((resolve) => setImmediate(resolve))
}

test('external cancellation stops the reader and settles without starting fallback polling', async () => {
  globalThis.__taskStreamProbe = {
    pollCalls: 0,
    readerCancelled: 0,
    streamSignal: null,
    resolveRead: null,
  }
  const clientUrl = moduleUrl(`
    export class ApiError extends Error {}
    export const BASE_URL = () => 'http://backend'
    export const toApiResult = async (promise) => {
      try { return { data: await promise, error: null } }
      catch (error) { return { data: null, error } }
    }
    export const requireData = async (promise) => {
      const result = await promise
      if (result.error) throw result.error
      return result.data
    }
    export const apiFetch = async (_path, options) => {
      globalThis.__taskStreamProbe.pollCalls += 1
      return new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(new Error('poll aborted')), { once: true })
      })
    }
    export const authenticatedFetch = async (_url, options) => {
      globalThis.__taskStreamProbe.streamSignal = options.signal
      return {
        ok: true,
        body: {
          getReader() {
            return {
              read: () => new Promise((resolve) => { globalThis.__taskStreamProbe.resolveRead = resolve }),
              cancel: async () => {
                globalThis.__taskStreamProbe.readerCancelled += 1
                globalThis.__taskStreamProbe.resolveRead?.({ done: true })
              },
            }
          },
        },
      }
    }
  `)
  const eventStateUrl = moduleUrl(`
    export const dispatchTaskProgress = (event, onProgress) => {
      if (event.status === 'completed') return 'completed'
      if (event.status === 'failed') return 'failed'
      onProgress?.(event)
      return 'progress'
    }
  `)
  const { tasksApi } = await import(compileTasks(clientUrl, eventStateUrl))
  const controller = new AbortController()
  const resultPromise = tasksApi.stream('task-1', undefined, controller.signal)

  await nextTurn()
  assert.equal(globalThis.__taskStreamProbe.pollCalls, 1, 'the initial status poll should start')
  controller.abort()
  const result = await resultPromise
  await nextTurn()

  assert.equal(globalThis.__taskStreamProbe.streamSignal.aborted, true)
  assert.equal(globalThis.__taskStreamProbe.readerCancelled, 1, 'cancellation must cancel a pending stream reader')
  assert.equal(result.data, null)
  assert.match(result.error?.message ?? '', /已取消/)
  assert.equal(globalThis.__taskStreamProbe.pollCalls, 1, 'an aborted stream must not fall back to another poll')
  delete globalThis.__taskStreamProbe
})

test('assistant exposes stream cancellation through the stop control and component unmount', () => {
  const storeSource = fs.readFileSync(
    path.resolve(here, '../src/renderer/src/stores/assistant.ts'),
    'utf8',
  )
  const componentSource = fs.readFileSync(
    path.resolve(here, '../src/renderer/src/components/AiAssistant.vue'),
    'utf8',
  )
  assert.match(storeSource, /\bsend,\s*\n\s*abortStream,/)
  assert.match(componentSource, /v-if="assistant\.sending"[\s\S]*@click="stopSending"/)
  assert.match(componentSource, /function stopSending\(\): void \{[\s\S]*assistant\.abortStream\(\)/)
  assert.match(componentSource, /onUnmounted\(\(\) => \{[\s\S]*assistant\.abortStream\(\)/)
})

test('recognition unmount owns task waits and clears its live recognition pages', () => {
  const recognizeSource = fs.readFileSync(
    path.resolve(here, '../src/renderer/src/views/RecognizeView.vue'),
    'utf8',
  )
  assert.match(recognizeSource, /const recognitionWaitControllers = new Set<AbortController>\(\)/)
  assert.match(recognizeSource, /tasksApi\.stream\(taskId,[\s\S]*controller\.signal\)/)
  assert.match(
    recognizeSource,
    /onUnmounted\(\(\) => \{[\s\S]*controller\.abort\(\)[\s\S]*clearLiveRecognitionPage\(pageId\)/,
  )
})

test('recognition validates completed task results before using pipeline or AI fields', () => {
  const recognizeSource = fs.readFileSync(
    path.resolve(here, '../src/renderer/src/views/RecognizeView.vue'),
    'utf8',
  )
  assert.doesNotMatch(recognizeSource, /waitForTaskResult<[A-Za-z]+Response>/)
  assert.match(
    recognizeSource,
    /const result = await waitForTaskResult\(submitted\.task_id, target\.pageId\)[\s\S]*if \(!isPipelineResponse\(result\)\)/,
  )
  assert.match(
    recognizeSource,
    /const response = await waitForTaskResult\(submitted\.task_id, target\.pageId\)[\s\S]*if \(!isAiTranscribeResponse\(response\)\)/,
  )
  assert.doesNotMatch(recognizeSource, /return completed\.result as/)
})

test('live recognition state is released after its owning page is cleared', async () => {
  const sourcePath = path.resolve(here, '../src/renderer/src/utils/liveRecognitionState.ts')
  const state = await import(compileTypeScript(sourcePath))

  state.registerLiveRecognitionPage('page-1', 101)
  state.updateLiveRecognitionPage('page-1', {
    taskId: 'task-1',
    progressPercent: 42,
  })
  assert.deepEqual(state.liveRecognitionTaskPatch(101, 'processing'), {
    taskId: 'task-1',
    status: 'processing',
    progressPercent: 42,
    progressMessage: '',
    errorMessage: '',
  })

  state.clearLiveRecognitionPage('page-1')
  assert.deepEqual(state.liveRecognitionTaskPatch(101, 'processing'), {})
})
