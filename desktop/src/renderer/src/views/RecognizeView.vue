<template>
  <div class="recognize-view">
    <div class="rv-header">
      <div class="rv-title">
        <h2>智能识别</h2>
        <p>上传乐谱图片或 PDF，快速得到简谱成果</p>
      </div>
      <div v-if="store.pageCount" class="page-nav">
        <n-button size="small" quaternary :disabled="!store.canPrevPage" @click="store.prevPage()">
          <template #icon><n-icon><ChevronBackOutline /></n-icon></template>
        </n-button>
        <span class="page-indicator">{{ store.currentPageIndex + 1 }} / {{ store.pageCount }}</span>
        <n-button size="small" quaternary :disabled="!store.canNextPage" @click="store.nextPage()">
          <template #icon><n-icon><ChevronForwardOutline /></n-icon></template>
        </n-button>
      </div>
    </div>

    <file-uploader @uploaded="onFileUploaded" />

    <n-progress
      v-if="store.activePageTaskCount"
      type="line"
      :percentage="overallProgressPercent"
      :indicator-placement="'inside'"
      processing
      class="rv-progress"
    >
      {{ overallProgressText }}
    </n-progress>

    <MeasureNumberPicker
      v-model:show="pickerShow"
      :options="pickerOptions"
      @confirm="onPickerConfirm"
      @cancel="onPickerCancel"
    />

    <div class="rv-actions">
      <n-button
        type="primary"
        @click="recognize"
        :loading="currentPageProcessing"
        :disabled="!store.hasInput || currentPageProcessing"
      >
        <template #icon><n-icon><ScanOutline /></n-icon></template>
        识别并自动填充
      </n-button>
      <n-button
        @click="recognizeAllPages"
        :loading="store.activePageTaskCount > 0"
        :disabled="!pendingRecognizableCount"
        secondary
      >
        <template #icon><n-icon><FlashOutline /></n-icon></template>
        批量识别全部
      </n-button>
      <div class="ai-switch">
        <span>AI 视觉检测</span>
        <n-switch v-model:value="aiVisionEnabled" size="small" />
      </div>
    </div>

    <div v-if="store.pages.length" class="pages-strip">
      <div
        v-for="(page, index) in store.pages"
        :key="page.id"
        :class="['page-card', page.status, { active: index === store.currentPageIndex }]"
        @click="store.selectPage(index)"
      >
        <button
          v-if="page.status !== 'waiting'"
          class="page-del"
          type="button"
          :disabled="page.status === 'processing'"
          @click.stop="removePage(index)"
        >
          <n-icon size="12"><CloseOutline /></n-icon>
        </button>
        <button
          v-else
          class="page-waiting-action"
          type="button"
          title="选择起始小节号"
          @click.stop="openMeasurePickerForPage(page)"
        >
          <n-icon size="12"><AlertCircleOutline /></n-icon>
          <span>待选择</span>
        </button>
        <div class="page-thumb">
          <img
            v-if="isPreviewable(page.inputFileName)"
            :src="getFileURL(page.inputFileId)"
            :alt="page.inputFileName"
          />
          <n-icon v-else size="20" class="page-icon"><DocumentOutline /></n-icon>
        </div>
        <div class="page-label">
          <span class="page-name">{{ page.inputFileName }}</span>
          <span :class="['page-status', page.status]">{{ statusText(page) }}</span>
        </div>
        <div v-if="page.status === 'processing'" class="page-mini-progress">
          <span :style="{ width: `${Math.max(4, page.progressPercent)}%` }" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { pipelineApi } from '../api/pipeline'
import { renderApi } from '../api/render'
import { aiApi } from '../api/ai'
import { tasksApi } from '../api/tasks'
import { historyApi } from '../api/history'
import { getFileURL } from '../api/client'
import type {
  AiTranscribeResponse,
  AiTranscribedPage,
  PipelineResponse,
  SSEProgressEvent,
} from '../models/types'
import type { TaskPage, TaskPageInput } from '../stores/task'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { notifyHistoryUpdated } from '../utils/historyEvents'
import FileUploader from '../components/FileUploader.vue'
import MeasureNumberPicker from '../components/MeasureNumberPicker.vue'
import {
  ScanOutline,
  FlashOutline,
  CloseOutline,
  AlertCircleOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  DocumentOutline,
} from '@vicons/ionicons5'
import { NButton, NIcon, NProgress, NSwitch, useMessage } from 'naive-ui'

type RecognitionMode = 'omr' | 'ai'

interface RecognitionTarget {
  pageId: string
  inputFileName: string
  inputFileId: string
  startMeasureNumber: number | null
}

interface PageResult {
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  start_measure_number: number | null
  status: string
  error_message: string
}

const store = useTaskStore()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()
const aiVisionEnabled = ref(false)
const pickerShow = ref(false)
const pickerOptions = ref<number[]>([])
const pickerPageId = ref<string | null>(null)

const activePages = computed(() => store.pages.filter((page) => page.status === 'processing'))
const currentPageProcessing = computed(() => store.currentPage?.status === 'processing')
const pendingRecognizableCount = computed(() => store.pages.filter((page) => isStartablePage(page)).length)
const overallProgressPercent = computed(() => {
  if (!activePages.value.length) return 0
  const total = activePages.value.reduce((sum, page) => sum + page.progressPercent, 0)
  return Math.round(total / activePages.value.length)
})
const overallProgressText = computed(() => {
  if (activePages.value.length === 1) {
    return activePages.value[0].progressMessage || '后台处理中'
  }
  return `${activePages.value.length} 个后台任务并行处理中`
})

function isPreviewable(fileName: string): boolean {
  return /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(fileName)
}

function isStartablePage(page: TaskPage): boolean {
  return !!page.inputFileId && page.status !== 'processing' && page.status !== 'waiting'
}

function statusText(page: TaskPage): string {
  if (page.status === 'processing') {
    return page.progressPercent > 0 ? `${Math.round(page.progressPercent)}%` : '处理中'
  }
  const map: Record<string, string> = { completed: '完成', failed: '失败', pending: '待处理', waiting: '待选择' }
  return map[page.status] ?? ''
}

function removePage(index: number): void {
  const page = store.pages[index]
  if (!page) return
  if (page.status === 'processing') {
    message.warning('后台识别中的页面暂不能移除')
    return
  }
  store.removePage(index)
  log.addLog(`已移除：${page.inputFileName}`)
}

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  store.addInputPage(fileName, fileId)
  log.addLog(`已加入：${fileName}`)
}

function openMeasurePickerForPage(page: TaskPage): void {
  if (page.status !== 'waiting') return
  if (!page.measureNumberOptions.length) {
    message.warning('没有可选的小节号候选')
    return
  }
  pickerPageId.value = page.id
  pickerOptions.value = page.measureNumberOptions
  pickerShow.value = true
}

async function onPickerConfirm(value: number): Promise<void> {
  const pageId = pickerPageId.value
  pickerShow.value = false
  pickerPageId.value = null
  if (!pageId) return
  await applyMeasureSelection(pageId, value)
}

function onPickerCancel(): void {
  pickerShow.value = false
  pickerPageId.value = null
}

async function recognize(): Promise<void> {
  const page = store.currentPage
  if (!page || !isStartablePage(page)) return
  await submitRecognitionTargets([targetFromPage(page)], aiVisionEnabled.value ? 'ai' : 'omr')
}

async function recognizeAllPages(): Promise<void> {
  const targets = store.pages
    .filter((page) => isStartablePage(page))
    .map(targetFromPage)
  if (!targets.length) return
  await submitRecognitionTargets(targets, aiVisionEnabled.value ? 'ai' : 'omr')
}

function targetFromPage(page: TaskPage): RecognitionTarget {
  return {
    pageId: page.id,
    inputFileName: page.inputFileName,
    inputFileId: page.inputFileId,
    startMeasureNumber: page.startMeasureNumber,
  }
}

async function submitRecognitionTargets(targets: RecognitionTarget[], mode: RecognitionMode): Promise<void> {
  const historyPageIds = await createPendingHistory(targets)
  const label = mode === 'ai' ? 'AI 视觉检测' : 'OMR 识别'

  for (const target of targets) {
    const historyPageId = historyPageIds.get(target.pageId) ?? null
    store.beginBackgroundTask()
    const run = mode === 'ai'
      ? runAiTarget(target, historyPageId)
      : runPipelineTarget(target, historyPageId)
    void run.finally(() => {
      store.endBackgroundTask()
    })
  }

  message.success(`已提交 ${targets.length} 个${label}后台任务`)
}

async function createPendingHistory(targets: RecognitionTarget[]): Promise<Map<string, number>> {
  const result = new Map<string, number>()
  try {
    const created = await historyApi.create({
      pages: targets.map((target) => ({
        input_file_name: target.inputFileName,
        input_file_id: target.inputFileId,
        start_measure_number: target.startMeasureNumber,
        status: 'processing',
        error_message: '',
      })),
    })
    created.pages.forEach((page, index) => {
      const target = targets[index]
      if (!target) return
      result.set(target.pageId, page.id)
      store.patchPageById(target.pageId, { historyPageId: page.id })
    })
    notifyHistoryUpdated()
  } catch (error: unknown) {
    log.addLog(`创建后台历史记录失败：${errorMessage(error)}`, 'warn')
  }
  return result
}

async function runPipelineTarget(target: RecognitionTarget, historyPageId: number | null): Promise<void> {
  markPageProcessing(target, '读取输入文件', 3)
  try {
    const resp = await fetch(getFileURL(target.inputFileId))
    if (!resp.ok) throw new Error(`读取文件失败：${resp.status}`)
    const blob = await resp.blob()

    markPageProcessing(target, '提交 OMR 后台任务', 8)
    const submitted = await pipelineApi.run(
      new File([blob], target.inputFileName),
      settings.targetKey,
      target.startMeasureNumber ?? undefined,
    )
    store.patchPageById(target.pageId, { taskId: submitted.task_id })

    const result = await waitForTaskResult<PipelineResponse>(submitted.task_id, target.pageId)
    const split = splitJianpuAndOcr(result.jianpu_text)
    const needsMeasureChoice = target.startMeasureNumber == null && result.ocr_measure_numbers.length > 0
    const resultStatus = needsMeasureChoice ? 'waiting' : 'completed'
    const waitingMessage = needsMeasureChoice
      ? waitingMeasureMessage(result.ocr_measure_numbers)
      : ''
    const pageResult: PageResult = {
      input_file_name: target.inputFileName,
      input_file_id: target.inputFileId,
      musicxml_file_id: result.musicxml_file_id,
      jianpu_text: split.jianpuText,
      ocr_text: split.ocrText,
      svg_file_id: result.svg_file_id,
      start_measure_number: target.startMeasureNumber,
      status: resultStatus,
      error_message: waitingMessage,
    }

    store.patchPageById(target.pageId, {
      musicxmlFileId: result.musicxml_file_id,
      musicxmlText: '',
      jianpuText: split.jianpuText,
      ocrText: split.ocrText,
      jianpuDirty: false,
      svgFileId: result.svg_file_id,
      originalFileName: isPreviewable(target.inputFileName) ? target.inputFileName : '',
      originalFileId: isPreviewable(target.inputFileName) ? target.inputFileId : '',
      taskId: '',
      status: resultStatus,
      progressPercent: 100,
      progressMessage: needsMeasureChoice ? '等待选择起始小节号' : '识别完成',
      measureNumberOptions: needsMeasureChoice ? result.ocr_measure_numbers : [],
      errorMessage: waitingMessage,
    })
    await persistPageResult(target, pageResult, historyPageId)
    if (needsMeasureChoice) {
      log.addLog(`等待选择起始小节号：${target.inputFileName}`, 'warn')
      message.warning(`等待选择起始小节号：${target.inputFileName}`)
    } else {
      log.addLog(`识别完成：${target.inputFileName}`)
      message.success(`识别完成：${target.inputFileName}`)
    }
  } catch (error: unknown) {
    await failTarget(target, historyPageId, error, '识别失败')
  }
}

async function applyMeasureSelection(pageId: string, selected: number): Promise<void> {
  const page = store.pages.find((entry) => entry.id === pageId)
  if (!page) return

  store.patchPageById(pageId, {
    status: 'processing',
    startMeasureNumber: selected,
    progressPercent: 92,
    progressMessage: '应用起始小节号',
    errorMessage: '',
  })

  let svgFileId = page.svgFileId
  try {
    if (page.musicxmlFileId && selected !== page.measureNumberOptions[0]) {
      const rendered = await renderApi.jianpuSvg({
        musicxml_file_id: page.musicxmlFileId,
        page_image_file_id: page.originalFileId || page.inputFileId || undefined,
        target_key: settings.targetKey,
        start_measure_number: selected,
      })
      svgFileId = rendered.svg_file_id
    }

    store.patchPageById(pageId, {
      svgFileId,
      status: 'completed',
      progressPercent: 100,
      progressMessage: '识别完成',
      measureNumberOptions: [],
      errorMessage: '',
    })
    await persistPageResult(targetFromPage({ ...page, startMeasureNumber: selected }), {
      input_file_name: page.inputFileName,
      input_file_id: page.inputFileId,
      musicxml_file_id: page.musicxmlFileId,
      jianpu_text: page.jianpuText,
      ocr_text: page.ocrText,
      svg_file_id: svgFileId,
      start_measure_number: selected,
      status: 'completed',
      error_message: '',
    }, page.historyPageId)
    log.addLog(`已选择起始小节号：${page.inputFileName} -> ${selected}`)
    message.success('已应用起始小节号')
  } catch (error: unknown) {
    const msg = errorMessage(error)
    store.patchPageById(pageId, {
      status: 'waiting',
      progressPercent: 100,
      progressMessage: '等待选择起始小节号',
      errorMessage: msg,
    })
    message.error(msg)
  }
}

async function runAiTarget(target: RecognitionTarget, historyPageId: number | null): Promise<void> {
  markPageProcessing(target, '提交 AI 视觉检测任务', 5)
  try {
    const submitted = await aiApi.transcribe({
      file_id: target.inputFileId,
      target_key: settings.targetKey,
      normalize: true,
    })
    store.patchPageById(target.pageId, { taskId: submitted.task_id })

    const response = await waitForTaskResult<AiTranscribeResponse>(submitted.task_id, target.pageId)
    if (!response.pages.length) throw new Error('AI 未返回任何页面')

    const warnings = collectAiWarnings(response.pages, response.warnings)
    applyAiResult(target, response, historyPageId)

    const pageResult: PageResult = {
      input_file_name: target.inputFileName,
      input_file_id: target.inputFileId,
      musicxml_file_id: '',
      jianpu_text: response.merged_jianpu_text,
      ocr_text: '',
      svg_file_id: '',
      start_measure_number: target.startMeasureNumber,
      status: 'completed',
      error_message: warnings.join('；'),
    }
    await persistPageResult(target, pageResult, historyPageId)
    log.addLog(`AI 转写完成：${target.inputFileName}`)
    if (warnings.length) {
      message.warning(warnings.slice(0, 3).join('；'))
    } else {
      message.success(`AI 转写完成：${target.inputFileName}`)
    }
  } catch (error: unknown) {
    await failTarget(target, historyPageId, error, 'AI 转写失败')
  }
}

function applyAiResult(
  target: RecognitionTarget,
  response: AiTranscribeResponse,
  historyPageId: number | null,
): void {
  if (response.pages.length === 1) {
    const page = response.pages[0]
    const warningText = aiPageErrorMessage(page)
    store.patchPageById(target.pageId, {
      inputFileName: aiPageLabel(response.source_filename, page, response.pages.length),
      inputFileId: page.page_image_file_id,
      originalFileName: aiPageLabel(response.source_filename, page, response.pages.length),
      originalFileId: page.page_image_file_id,
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: page.jianpu_text,
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      taskId: '',
      status: 'completed',
      progressPercent: 100,
      progressMessage: 'AI 转写完成',
      errorMessage: warningText,
    })
    return
  }

  const aiPages: TaskPageInput[] = response.pages.map((page, index) => {
    const label = aiPageLabel(response.source_filename, page, response.pages.length)
    return {
      inputFileName: label,
      historyPageId: index === 0 ? historyPageId : null,
      inputFileId: page.page_image_file_id,
      originalFileName: label,
      originalFileId: page.page_image_file_id,
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: page.jianpu_text,
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      status: 'completed',
      progressPercent: 100,
      progressMessage: 'AI 转写完成',
      errorMessage: aiPageErrorMessage(page),
    }
  })
  store.replacePageByIdKeepingSelection(target.pageId, aiPages)
}

async function waitForTaskResult<T>(taskId: string, pageId: string): Promise<T> {
  const completed = await tasksApi.stream(taskId, (event) => {
    updatePageProgress(pageId, event)
  })
  if (!completed.result) {
    throw new Error('任务完成但没有返回结果')
  }
  return completed.result as T
}

function updatePageProgress(pageId: string, event: SSEProgressEvent): void {
  const failed = event.status === 'failed'
  store.patchPageById(pageId, {
    taskId: event.task_id,
    status: failed ? 'failed' : 'processing',
    progressPercent: Math.max(0, Math.min(99, Math.round(event.percent))),
    progressMessage: taskProgressText(event),
    errorMessage: failed ? taskProgressText(event) : '',
  })
}

function markPageProcessing(target: RecognitionTarget, messageText: string, percent: number): void {
  store.patchPageById(target.pageId, {
    status: 'processing',
    progressPercent: percent,
    progressMessage: messageText,
    errorMessage: '',
  })
}

async function failTarget(
  target: RecognitionTarget,
  historyPageId: number | null,
  error: unknown,
  prefix: string,
): Promise<void> {
  const msg = errorMessage(error)
  store.patchPageById(target.pageId, {
    taskId: '',
    status: 'failed',
    progressPercent: 100,
    progressMessage: msg,
    errorMessage: msg,
  })
  await persistPageResult(target, {
    input_file_name: target.inputFileName,
    input_file_id: target.inputFileId,
    musicxml_file_id: '',
    jianpu_text: '',
    ocr_text: '',
    svg_file_id: '',
    start_measure_number: target.startMeasureNumber,
    status: 'failed',
    error_message: msg,
  }, historyPageId)
  log.addError(`${prefix}：${target.inputFileName}：${msg}`)
  message.error(`${target.inputFileName}：${msg}`)
}

async function persistPageResult(
  target: RecognitionTarget,
  result: PageResult,
  historyPageId: number | null,
): Promise<void> {
  try {
    if (historyPageId) {
      await historyApi.updatePage(historyPageId, {
        musicxml_file_id: result.musicxml_file_id,
        jianpu_text: result.jianpu_text,
        ocr_text: result.ocr_text,
        svg_file_id: result.svg_file_id,
        start_measure_number: result.start_measure_number,
        status: result.status,
        error_message: result.error_message,
      })
    } else {
      const created = await historyApi.create({
        pages: [{
          input_file_name: result.input_file_name,
          input_file_id: result.input_file_id,
          musicxml_file_id: result.musicxml_file_id,
          jianpu_text: result.jianpu_text,
          ocr_text: result.ocr_text,
          svg_file_id: result.svg_file_id,
          start_measure_number: result.start_measure_number,
          status: result.status,
          error_message: result.error_message,
        }],
      })
      const pageId = created.pages[0]?.id
      if (pageId) {
        store.patchPageById(target.pageId, { historyPageId: pageId })
      }
    }
    notifyHistoryUpdated()
  } catch (error: unknown) {
    log.addLog(`保存后台历史结果失败：${errorMessage(error)}`, 'warn')
  }
}

function aiPageLabel(sourceName: string, page: AiTranscribedPage, totalPages: number): string {
  if (totalPages <= 1 && !/\.pdf$/i.test(sourceName)) return sourceName
  const stem = sourceName.replace(/\.[^.]+$/, '')
  return `${stem}_page_${String(page.page_index + 1).padStart(3, '0')}.png`
}

function aiPageErrorMessage(page: AiTranscribedPage): string {
  return [...page.validation_errors, ...page.warnings].join('；')
}

function collectAiWarnings(pages: AiTranscribedPage[], responseWarnings: string[]): string[] {
  return [
    ...responseWarnings,
    ...pages.flatMap((page) => [...page.validation_errors, ...page.warnings]),
  ]
}

function taskProgressText(event: SSEProgressEvent): string {
  if (event.status === 'failed') return event.error || event.message || '任务失败'
  return event.message || event.stage || '处理中'
}

function waitingMeasureMessage(options: number[]): string {
  return `等待选择起始小节号：${options.join('、')}`
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
</script>

<style scoped>
.recognize-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 900px;
  margin: 0 auto;
  min-height: 100%;
  justify-content: center;
}

.rv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rv-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.rv-header p {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 0;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-indicator {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 40px;
  text-align: center;
}

.rv-progress {
  margin: 0;
}

.rv-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-switch {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 12px;
}

.pages-strip {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding: 4px 0;
}

.page-card {
  width: 110px;
  position: relative;
  cursor: pointer;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--border);
  background: var(--bg-elevated);
  padding: 6px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.page-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.page-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.page-card.processing {
  border-color: var(--warning);
}

.page-card.waiting {
  border-color: var(--warning);
  box-shadow: 0 0 0 1px rgba(250, 176, 5, 0.35);
}

.page-card.failed {
  border-color: var(--danger);
}

.page-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: var(--bg-base);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.12s ease, background-color 0.12s ease, color 0.12s ease;
  z-index: 2;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.page-card:hover .page-del {
  opacity: 1;
}

.page-del:hover {
  background: var(--danger);
  color: #fff;
}

.page-del:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.page-waiting-action {
  position: absolute;
  top: 2px;
  right: 2px;
  height: 20px;
  border: 0;
  border-radius: 999px;
  background: var(--warning);
  color: #1f2937;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  padding: 0 6px;
  cursor: pointer;
  font-size: 10px;
  font-weight: 600;
  z-index: 2;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}

.page-waiting-action:hover {
  filter: brightness(0.96);
}

.page-thumb {
  width: 100%;
  height: 64px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
}

.page-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.page-icon {
  color: var(--text-tertiary);
}

.page-label {
  margin-top: 4px;
  text-align: center;
}

.page-name {
  display: block;
  font-size: 10px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.page-status {
  font-size: 10px;
  color: var(--text-tertiary);
}

.page-status.completed { color: var(--success); }
.page-status.failed { color: var(--danger); }
.page-status.processing { color: var(--warning); }
.page-status.waiting { color: var(--warning); }

.page-mini-progress {
  height: 2px;
  margin-top: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--bg-surface);
}

.page-mini-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--warning);
  transition: width 0.2s ease;
}

.rv-preview {
  border-radius: var(--radius-lg);
}
</style>
