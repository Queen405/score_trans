<template>
  <div class="recognize-view">
    <div class="rv-header">
      <div class="rv-title">
        <h2>智能识别</h2>
      </div>
    </div>

    <MeasureNumberPicker
      v-model:show="pickerShow"
      :options="pickerOptions"
      @confirm="onPickerConfirm"
      @cancel="onPickerCancel"
    />

    <div class="dashboard-grid">
      <!-- 智能识别 -->
      <div class="dashboard-card card-recognition">
        <div class="card-header">
          <div class="card-title">
            <n-icon size="18"><ScanOutline /></n-icon>
            <span>智能识别</span>
          </div>
          <div class="card-header-right">
            <n-select
              v-if="store.batches.length > 1"
              :value="store.currentBatchId"
              :options="batchOptions"
              size="small"
              class="batch-select"
              @update:value="store.selectBatch($event)"
            />
            <div v-if="store.pageCount" class="page-nav">
              <n-button size="small" quaternary :disabled="!store.canPrevPage" @click="store.prevPage()">
                <template #icon><n-icon><ChevronBackOutline /></n-icon></template>
              </n-button>
              <span class="page-indicator">{{ currentBatchLocalIndex + 1 }} / {{ store.pageCount }}</span>
              <n-button size="small" quaternary :disabled="!store.canNextPage" @click="store.nextPage()">
                <template #icon><n-icon><ChevronForwardOutline /></n-icon></template>
              </n-button>
            </div>
          </div>
        </div>
        <div class="card-body">
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
          <div v-if="waitingPageCount" class="rv-waiting-banner">
            {{ waitingPageCount }} 个页面等待选择起始小节号，点击卡片上的"待选择"按钮进行操作
          </div>
        </div>
        <div class="card-footer">
          <n-button
            type="primary"
            size="small"
            @click="recognize"
            :loading="recognizeButtonLoading"
            :disabled="recognizeButtonDisabled"
          >
            <template #icon><n-icon><ScanOutline /></n-icon></template>
            {{ recognizeButtonText }}
          </n-button>
          <n-button
            size="small"
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
          <div class="preprocess-inline">
            <span class="preprocess-label">启用预处理</span>
            <n-switch v-model:value="settings.omrPreprocess" size="small" />
            <n-input-number
              v-model:value="settings.omrPreprocessLongEdge"
              :min="0"
              :step="200"
              size="small"
              style="width: 110px"
              :disabled="!settings.omrPreprocess"
            />
            <span class="preprocess-label">黑白化</span>
            <n-switch v-model:value="settings.omrPreprocessBinarize" size="small" :disabled="!settings.omrPreprocess" />
          </div>
          <span v-if="selectedPageCount" class="selection-count">已选 {{ selectedPageCount }}</span>
        </div>
      </div>

      <!-- 项目统计 -->
      <div class="dashboard-card card-stats">
        <div class="card-title">项目统计</div>
        <div class="stats-body">
          <div class="stats-ring-wrap">
            <div class="stats-ring">
              <svg viewBox="0 0 36 36">
                <path
                  class="ring-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  v-if="statsTotal > 0"
                  class="ring-segment ring-completed"
                  :stroke-dasharray="`${(statsCompleted / statsTotal) * 100} ${100 - (statsCompleted / statsTotal) * 100}`"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  v-if="statsTotal > 0"
                  class="ring-segment ring-processing"
                  :stroke-dasharray="`${(statsProcessing / statsTotal) * 100} ${100 - (statsProcessing / statsTotal) * 100}`"
                  :stroke-dashoffset="`${-(statsCompleted / statsTotal) * 100}`"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  v-if="statsTotal > 0"
                  class="ring-segment ring-failed"
                  :stroke-dasharray="`${(statsFailed / statsTotal) * 100} ${100 - (statsFailed / statsTotal) * 100}`"
                  :stroke-dashoffset="`${-((statsCompleted + statsProcessing) / statsTotal) * 100}`"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <div class="ring-center">
                <span class="ring-total">{{ statsTotal }}</span>
                <span class="ring-label">总计</span>
              </div>
            </div>
            <div class="stats-legend">
              <div class="legend-item">
                <span class="legend-dot dot-completed" />
                <span class="legend-text">完成</span>
                <span class="legend-value">{{ statsCompleted }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot dot-processing" />
                <span class="legend-text">处理中</span>
                <span class="legend-value">{{ statsProcessing }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot dot-failed" />
                <span class="legend-text">失败</span>
                <span class="legend-value">{{ statsFailed }}</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot dot-waiting" />
                <span class="legend-text">等待</span>
                <span class="legend-value">{{ statsWaiting }}</span>
              </div>
            </div>
          </div>
          <div class="stats-mini-cards">
            <div class="mini-card">
              <span class="mini-card-value">{{ statsCompleted }}</span>
              <span class="mini-card-label">完成数</span>
            </div>
            <div class="mini-card">
              <span class="mini-card-value">{{ statsFailed }}</span>
              <span class="mini-card-label">失败数</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 最近上传 -->
      <div class="dashboard-card card-uploads">
        <div class="card-title">最近上传</div>
        <div v-if="store.currentBatchPages.length" class="uploads-list">
          <div
            v-for="page in store.currentBatchPages"
            :key="page.id"
            :class="['upload-card', page.status, {
              active: page.id === store.currentPage?.id,
              selected: isPageSelected(page.id),
            }]"
            @click="handlePageCardClick(page)"
          >
            <n-icon v-if="isPageSelected(page.id)" size="14" class="upload-selected-mark">
              <CheckmarkCircleOutline />
            </n-icon>
            <button
              v-if="page.status === 'failed' && !page.inputFileId"
              class="upload-reupload"
              type="button"
              title="重新上传"
              @click.stop="reuploadForPage(page)"
            >
              <n-icon size="12"><CloudUploadOutline /></n-icon>
            </button>
            <button
              v-else-if="page.status !== 'waiting'"
              class="upload-del"
              type="button"
              :disabled="page.status === 'processing'"
              @click.stop="removePageById(page.id)"
            >
              <n-icon size="12"><CloseOutline /></n-icon>
            </button>
            <button
              v-else
              class="upload-waiting-action"
              type="button"
              title="选择起始小节号"
              @click.stop="openMeasurePickerForPage(page)"
            >
              <n-icon size="12"><AlertCircleOutline /></n-icon>
              <span>待选择</span>
            </button>
            <div class="upload-thumb">
              <img
                v-if="active && isPreviewable(page.inputFileName)"
                :src="getFileURL(page.inputFileId)"
                :alt="page.inputFileName"
              />
              <n-icon v-else size="24" class="upload-icon"><DocumentOutline /></n-icon>
            </div>
            <div class="upload-info">
              <span class="upload-name">{{ page.inputFileName }}</span>
              <span :class="['upload-status', page.status]">{{ statusText(page) }}</span>
            </div>
            <div v-if="page.status === 'processing'" class="upload-mini-progress">
              <span :style="{ width: `${Math.max(4, page.progressPercent)}%` }" />
            </div>
          </div>
        </div>
        <div v-else class="uploads-empty">
          <n-icon size="32" class="empty-icon"><CloudUploadOutline /></n-icon>
          <span>暂无上传文件</span>
        </div>
      </div>

      <!-- 最近活动 -->
      <div class="dashboard-card card-activity">
        <div class="card-title">最近活动</div>
        <div v-if="recentActivities.length" class="activity-list">
          <div
            v-for="activity in recentActivities"
            :key="activity.id"
            class="activity-item"
          >
            <div :class="['activity-icon', activity.level]">
              <n-icon size="14">
                <component :is="activityIcon(activity.level)" />
              </n-icon>
            </div>
            <div class="activity-content">
              <span class="activity-name">{{ activity.message }}</span>
              <span class="activity-time">{{ activity.time }}</span>
            </div>
          </div>
        </div>
        <div v-else class="activity-empty">
          <span>暂无活动记录</span>
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
import { filesApi } from '../api/files'
import { getFileURL } from '../api/client'
import type {
  AiTranscribeResponse,
  AiTranscribedPage,
  HistoryPage,
  PipelineResponse,
  SSEProgressEvent,
} from '../models/types'
import type { TaskPage, TaskPageInput, TaskPageStatus } from '../stores/task'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { notifyHistoryPagePatched, notifyHistoryUpdated, type HistoryPagePatchDetail } from '../utils/historyEvents'
import {
  clearLiveRecognitionPage,
  getLiveRecognitionHistoryPageId,
  liveRecognitionTaskPatch,
  registerLiveRecognitionPage,
  updateLiveRecognitionPage,
} from '../utils/liveRecognitionState'
import { useFileUpload } from '../composables/useFileUpload'
import FileUploader from '../components/FileUploader.vue'
import MeasureNumberPicker from '../components/MeasureNumberPicker.vue'
import {
  ScanOutline,
  FlashOutline,
  CloseOutline,
  AlertCircleOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CheckmarkCircleOutline,
  CloudUploadOutline,
  DocumentOutline,
  CheckmarkDoneOutline,
  WarningOutline,
  TimeOutline,
  CloseCircleOutline,
  InformationCircleOutline,
  OptionsOutline,
} from '@vicons/ionicons5'
import { NButton, NIcon, NInputNumber, NProgress, NSelect, NSwitch, useMessage } from 'naive-ui'

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
const selectedPageIds = ref<Set<string>>(new Set())
const reupload = useFileUpload()

withDefaults(defineProps<{
  active?: boolean
}>(), {
  active: true,
})

// ── Statistics ──
const statsTotal = computed(() => store.currentBatchPages.length)
const statsCompleted = computed(() => store.currentBatchPages.filter((p) => p.status === 'completed').length)
const statsProcessing = computed(() => store.currentBatchPages.filter((p) => p.status === 'processing').length)
const statsFailed = computed(() => store.currentBatchPages.filter((p) => p.status === 'failed').length)
const statsWaiting = computed(() => store.currentBatchPages.filter((p) => p.status === 'waiting').length)

// ── Recent Activity ──
interface ActivityItem {
  id: string
  message: string
  time: string
  level: 'info' | 'warn' | 'error' | 'success'
}

const recentActivities = computed((): ActivityItem[] => {
  const pages = store.currentBatchPages
  const activities: ActivityItem[] = []
  for (const page of [...pages].reverse().slice(0, 8)) {
    let message = ''
    let level: ActivityItem['level'] = 'info'
    if (page.status === 'completed') {
      message = `Processed: ${page.inputFileName}`
      level = 'success'
    } else if (page.status === 'failed') {
      message = `Failed: ${page.inputFileName}`
      level = 'error'
    } else if (page.status === 'processing') {
      message = `Processing: ${page.inputFileName}`
      level = 'info'
    } else if (page.status === 'waiting') {
      message = `Waiting: ${page.inputFileName}`
      level = 'warn'
    } else {
      message = `Pending: ${page.inputFileName}`
      level = 'info'
    }
    activities.push({
      id: page.id,
      message,
      time: page.progressMessage || statusText(page),
      level,
    })
  }
  return activities
})

function activityIcon(level: ActivityItem['level']) {
  switch (level) {
    case 'success': return CheckmarkDoneOutline
    case 'error': return CloseCircleOutline
    case 'warn': return WarningOutline
    case 'info': return InformationCircleOutline
    default: return TimeOutline
  }
}

const batchOptions = computed(() =>
  store.batches.map((b, i) => ({
    label: b.sealed ? `批次 ${i + 1}：${b.label}` : `草稿：${b.label}`,
    value: b.id,
  })),
)
const currentBatchLocalIndex = computed(() =>
  store.currentBatchPages.indexOf(store.currentPage!),
)
const activePages = computed(() => store.currentBatchPages.filter((page) => page.status === 'processing'))
const waitingPageCount = computed(() => store.currentBatchPages.filter((page) => page.status === 'waiting').length)
const pendingRecognizableCount = computed(() => store.currentBatchPages.filter((page) => isStartablePage(page)).length)
const selectedPages = computed(() =>
  store.currentBatchPages.filter((page) => selectedPageIds.value.has(page.id)),
)
const selectedPageCount = computed(() => selectedPages.value.length)
const selectedProcessingCount = computed(() =>
  selectedPages.value.filter((page) => page.status === 'processing').length,
)
const recognizeTargetPages = computed(() => {
  const selectedStartable = selectedPages.value.filter((page) => isStartablePage(page))
  if (selectedPages.value.length) return selectedStartable
  const page = store.currentPage
  return page && isStartablePage(page) ? [page] : []
})
const recognizeButtonLoading = computed(() =>
  selectedPages.value.length
    ? selectedProcessingCount.value > 0 && recognizeTargetPages.value.length === 0
    : store.currentPage?.status === 'processing',
)
const recognizeButtonDisabled = computed(() => recognizeTargetPages.value.length === 0)
const recognizeButtonText = computed(() =>
  selectedPages.value.length
    ? `识别选中 ${recognizeTargetPages.value.length || selectedPages.value.length} 张`
    : '识别并自动填充',
)
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
  if (page.status === 'failed' && !page.inputFileId) {
    return '需重新上传'
  }
  const map: Record<string, string> = { completed: '完成', failed: '失败', pending: '待处理', waiting: '待选择' }
  return map[page.status] ?? ''
}

function isPageSelected(pageId: string): boolean {
  return selectedPageIds.value.has(pageId)
}

function handlePageCardClick(page: TaskPage): void {
  store.selectPageById(page.id)
  const next = new Set(selectedPageIds.value)
  if (next.has(page.id)) {
    next.delete(page.id)
  } else {
    next.add(page.id)
  }
  selectedPageIds.value = next
}

function removePageSelection(pageId: string): void {
  if (!selectedPageIds.value.has(pageId)) return
  const next = new Set(selectedPageIds.value)
  next.delete(pageId)
  selectedPageIds.value = next
}

function removePageById(pageId: string): void {
  const idx = store.pages.findIndex((p) => p.id === pageId)
  if (idx < 0) return
  const page = store.pages[idx]!
  if (page.status === 'processing') {
    message.warning('后台识别中的页面暂不能移除')
    return
  }
  removePageSelection(pageId)
  store.removePage(idx)
  log.addLog(`已移除：${page.inputFileName}`)
}

async function onFileUploaded(fileId: string, fileName: string): Promise<void> {
  store.addInputPage(fileName, fileId)
  log.addLog(`已加入：${fileName}`)
}

function reuploadForPage(page: TaskPage): void {
  if (reupload.uploading.value) return
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.png,.jpg,.jpeg,.tif,.tiff,.musicxml,.xml,.mxl,.txt'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file) return
    log.addLog(`正在重新上传：${file.name}`)
    const result = await reupload.upload(file)
    if (result) {
      let fileId: string
      let fileName: string
      if (result.pages && result.pages.length > 0) {
        fileId = result.pages[0].file_id
        fileName = result.pages[0].filename
      } else {
        fileId = result.file_id
        fileName = result.filename
      }
      const previewable = isPreviewable(fileName)
      store.patchPageById(page.id, {
        inputFileId: fileId,
        inputFileName: fileName,
        originalFileId: previewable ? fileId : '',
        originalFileName: previewable ? fileName : '',
        musicxmlFileId: '',
        musicxmlText: '',
        jianpuText: '',
        ocrText: '',
        svgFileId: '',
        status: 'pending',
        errorMessage: '',
      })
      log.addLog(`重新上传成功：${fileName}`)
    } else {
      message.error('重新上传失败')
    }
  }
  input.click()
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
  const targets = recognizeTargetPages.value.map((page) => targetFromPage(page, { resetStartMeasure: true }))
  if (!targets.length) return
  await submitRecognitionTargets(targets, aiVisionEnabled.value ? 'ai' : 'omr')
}

async function recognizeAllPages(): Promise<void> {
  const targets = store.currentBatchPages
    .filter((page) => isStartablePage(page))
    .map((page) => targetFromPage(page, { resetStartMeasure: true }))
  if (!targets.length) return
  await submitRecognitionTargets(targets, aiVisionEnabled.value ? 'ai' : 'omr')
}

function targetFromPage(page: TaskPage, options: { resetStartMeasure?: boolean } = {}): RecognitionTarget {
  // Prefer originalFileId for re-recognition if the input temp file was cleaned up
  const fileId = page.originalFileId || page.inputFileId
  return {
    pageId: page.id,
    inputFileName: page.inputFileName,
    inputFileId: fileId,
    startMeasureNumber: options.resetStartMeasure ? null : (page.startMeasureNumber ?? null),
  }
}

async function submitRecognitionTargets(targets: RecognitionTarget[], mode: RecognitionMode): Promise<void> {
  // Check file existence before starting recognition
  const fileIds = targets.map((t) => t.inputFileId).filter(Boolean)
  if (fileIds.length) {
    try {
      const exists = await filesApi.existsMany(fileIds)
      const missing = targets.filter((t) => !exists[t.inputFileId])
      if (missing.length) {
        message.error(
          `${missing.length} 个页面的原始文件已丢失（后端重启或已清理），请重新上传：${missing.map((t) => t.inputFileName).join('、')}`
        )
        for (const t of missing) {
          store.patchPageById(t.pageId, {
            status: 'failed',
            errorMessage: '原始文件已丢失，请重新上传',
          })
        }
        // Only continue with files that still exist
        targets = targets.filter((t) => exists[t.inputFileId])
        if (!targets.length) return
      }
    } catch {
      // If backend is down, failTarget will catch it later
    }
  }

  // Only seal the batch if any target belongs to an unsealed batch (new upload scenario)
  const hasUnsealedPage = targets.some((t) => {
    const page = store.pages.find((p) => p.id === t.pageId)
    return page && !page.batchSealed
  })
  if (hasUnsealedPage) store.sealCurrentBatch()
  const historyPageIds = await createPendingHistory(targets)

  // Update existing history pages to 'processing' for re-recognition
  for (const target of targets) {
    const historyPageId = historyPageIds.get(target.pageId)
    if (historyPageId) {
      registerLiveRecognitionPage(target.pageId, historyPageId)
      patchRecognitionPage(target.pageId, {
        startMeasureNumber: target.startMeasureNumber,
        historyPageId,
      })
      try {
        await historyApi.updatePage(historyPageId, {
          start_measure_number: target.startMeasureNumber,
          status: 'processing',
          error_message: '',
        })
        notifyHistoryPagePatched({
          id: historyPageId,
          patch: {
            start_measure_number: target.startMeasureNumber,
            status: 'processing',
            error_message: '',
          },
        })
      } catch { /* best-effort */ }
    }
  }

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
  // Reuse existing historyPageId for re-recognition
  for (const target of targets) {
    const page = store.pages.find((p) => p.id === target.pageId)
    if (page?.historyPageId) {
      result.set(target.pageId, page.historyPageId)
    }
  }
  const newTargets = targets.filter((t) => !result.has(t.pageId))
  if (!newTargets.length) return result
  try {
    const created = await historyApi.create({
      pages: newTargets.map((target) => ({
        input_file_name: target.inputFileName,
        input_file_id: target.inputFileId,
        start_measure_number: target.startMeasureNumber,
        status: 'processing',
        error_message: '',
      })),
    })
    created.pages.forEach((page, index) => {
      const target = newTargets[index]
      if (!target) return
      result.set(target.pageId, page.id)
      store.patchPageById(target.pageId, { historyPageId: page.id })
      registerLiveRecognitionPage(target.pageId, page.id)
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
    markPageProcessing(target, '提交 OMR 后台任务', 8)

    let submitted: { task_id: string }
    if (target.inputFileId) {
      // Submit directly by file_id — no need to download and re-upload
      submitted = await pipelineApi.runByFileId({
        file_id: target.inputFileId,
        target_key: settings.targetKey,
        start_measure_number: target.startMeasureNumber ?? null,
      })
    } else {
      throw new Error('无输入文件 ID，请重新上传图片')
    }
    patchRecognitionPage(target.pageId, { taskId: submitted.task_id })
    updateLiveRecognitionPage(target.pageId, { taskId: submitted.task_id })

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

    patchRecognitionPage(target.pageId, {
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
    clearLiveRecognitionPage(target.pageId)
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
  if (page.historyPageId) {
    notifyHistoryPagePatched({
      id: page.historyPageId,
      patch: {
        start_measure_number: selected,
        status: 'processing',
        error_message: '正在重新渲染',
      },
    })
  }

  let svgFileId = page.svgFileId
  let jianpuText = page.jianpuText
  try {
    if (page.musicxmlFileId && selected !== page.measureNumberOptions[0]) {
      const rendered = await renderApi.jianpuSvg({
        musicxml_file_id: page.musicxmlFileId,
        page_image_file_id: page.originalFileId || page.inputFileId || undefined,
        target_key: settings.targetKey,
        start_measure_number: selected,
      })
      svgFileId = rendered.svg_file_id
    } else if (!page.musicxmlFileId && page.jianpuText.trim()) {
      const rendered = await renderApi.jianpuTextSvg({
        jianpu_text: page.jianpuText,
        page_image_file_id: page.originalFileId || page.inputFileId || undefined,
        include_ocr_text: false,
        title: page.inputFileName || 'AI 简谱',
        start_measure_number: selected,
      })
      svgFileId = rendered.svg_file_id
      jianpuText = rendered.jianpu_text || page.jianpuText
    }

    store.patchPageById(pageId, {
      svgFileId,
      jianpuText,
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
      jianpu_text: jianpuText,
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
    const failedMessage = failedMeasureSelectionMessage(page.measureNumberOptions, msg)
    store.patchPageById(pageId, {
      status: 'waiting',
      progressPercent: 100,
      progressMessage: '等待选择起始小节号',
      measureNumberOptions: page.measureNumberOptions,
      errorMessage: failedMessage,
    })
    if (page.historyPageId) {
      try {
        const updated = await historyApi.updatePage(page.historyPageId, {
          start_measure_number: selected,
          status: 'waiting',
          error_message: failedMessage,
        })
        syncStoreFromHistoryPage(pageId, updated)
        notifyHistoryPagePatched(historyPagePatchFromPage(updated))
      } catch (persistError: unknown) {
        log.addLog(`保存小节号失败状态失败：${errorMessage(persistError)}`, 'warn')
        notifyHistoryPagePatched({
          id: page.historyPageId,
          patch: {
            start_measure_number: selected,
            status: 'waiting',
            error_message: failedMessage,
          },
        })
      }
    }
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
    patchRecognitionPage(target.pageId, { taskId: submitted.task_id })
    updateLiveRecognitionPage(target.pageId, { taskId: submitted.task_id })

    const response = await waitForTaskResult<AiTranscribeResponse>(submitted.task_id, target.pageId)
    if (!response.pages.length) throw new Error('AI 未返回任何页面')

    const warnings = collectAiWarnings(response.pages, response.warnings)
    const measureOptions = target.startMeasureNumber == null ? aiMeasureOptions(response) : []
    const needsMeasureChoice = measureOptions.length > 0
    const resultStatus = needsMeasureChoice ? 'waiting' : 'completed'
    const waitingMessage = needsMeasureChoice ? waitingMeasureMessage(measureOptions) : ''
    applyAiResult(target, response, historyPageId, resultStatus, measureOptions)

    const pageResult: PageResult = {
      input_file_name: target.inputFileName,
      input_file_id: target.inputFileId,
      musicxml_file_id: '',
      jianpu_text: response.merged_jianpu_text,
      ocr_text: '',
      svg_file_id: '',
      start_measure_number: target.startMeasureNumber,
      status: resultStatus,
      error_message: waitingMessage || warnings.join('；'),
    }
    await persistPageResult(target, pageResult, historyPageId)
    clearLiveRecognitionPage(target.pageId)
    if (needsMeasureChoice) {
      log.addLog(`AI 转写等待选择起始小节号：${target.inputFileName}`, 'warn')
      message.warning(`AI 转写等待选择起始小节号：${target.inputFileName}`)
    } else if (warnings.length) {
      log.addLog(`AI 转写完成：${target.inputFileName}`)
      message.warning(warnings.slice(0, 3).join('；'))
    } else {
      log.addLog(`AI 转写完成：${target.inputFileName}`)
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
  resultStatus: TaskPageStatus,
  measureOptions: number[],
): void {
  if (response.pages.length === 1) {
    const page = response.pages[0]
    const pageMeasureOptions = resultStatus === 'waiting'
      ? aiPageMeasureOptions(page, measureOptions)
      : []
    const messageText = resultStatus === 'waiting'
      ? waitingMeasureMessage(pageMeasureOptions)
      : aiPageErrorMessage(page)
    patchRecognitionPage(target.pageId, {
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
      status: resultStatus,
      progressPercent: 100,
      progressMessage: resultStatus === 'waiting' ? '等待选择起始小节号' : 'AI 转写完成',
      measureNumberOptions: pageMeasureOptions,
      errorMessage: messageText,
    })
    return
  }

  const aiPages: TaskPageInput[] = response.pages.map((page, index) => {
    const label = aiPageLabel(response.source_filename, page, response.pages.length)
    const pageMeasureOptions = resultStatus === 'waiting'
      ? aiPageMeasureOptions(page, measureOptions)
      : []
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
      status: resultStatus,
      progressPercent: 100,
      progressMessage: resultStatus === 'waiting' ? '等待选择起始小节号' : 'AI 转写完成',
      measureNumberOptions: pageMeasureOptions,
      errorMessage: resultStatus === 'waiting'
        ? waitingMeasureMessage(pageMeasureOptions)
        : aiPageErrorMessage(page),
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

function patchRecognitionPage(pageId: string, patch: Partial<TaskPage>): void {
  if (store.patchPageById(pageId, patch)) return
  const historyPageId = getLiveRecognitionHistoryPageId(pageId)
  if (historyPageId) {
    store.patchPageByHistoryPageId(historyPageId, patch)
  }
}

function updatePageProgress(pageId: string, event: SSEProgressEvent): void {
  const failed = event.status === 'failed'
  const patch: Partial<TaskPage> = {
    taskId: event.task_id,
    status: failed ? 'failed' : 'processing',
    progressPercent: Math.max(0, Math.min(99, Math.round(event.percent))),
    progressMessage: taskProgressText(event),
    errorMessage: failed ? taskProgressText(event) : '',
  }
  patchRecognitionPage(pageId, patch)
  updateLiveRecognitionPage(pageId, {
    taskId: event.task_id,
    status: failed ? 'failed' : 'processing',
    progressPercent: patch.progressPercent ?? 0,
    progressMessage: patch.progressMessage ?? '',
    errorMessage: patch.errorMessage ?? '',
  })
  const page = store.pages.find((p) => p.id === pageId)
  const historyPageId = page?.historyPageId ?? getLiveRecognitionHistoryPageId(pageId)
  if (historyPageId) {
    notifyHistoryPagePatched({
      id: historyPageId,
      patch: {
        status: failed ? 'failed' : 'processing',
        error_message: failed ? taskProgressText(event) : '',
      },
    })
  }
}

function markPageProcessing(target: RecognitionTarget, messageText: string, percent: number): void {
  const patch: Partial<TaskPage> = {
    status: 'processing',
    startMeasureNumber: target.startMeasureNumber,
    progressPercent: percent,
    progressMessage: messageText,
    errorMessage: '',
  }
  patchRecognitionPage(target.pageId, patch)
  updateLiveRecognitionPage(target.pageId, {
    status: 'processing',
    progressPercent: percent,
    progressMessage: messageText,
    errorMessage: '',
  })
  const page = store.pages.find((p) => p.id === target.pageId)
  const historyPageId = page?.historyPageId ?? getLiveRecognitionHistoryPageId(target.pageId)
  if (historyPageId) {
    notifyHistoryPagePatched({
      id: historyPageId,
      patch: { status: 'processing', error_message: '' },
    })
  }
}

async function failTarget(
  target: RecognitionTarget,
  historyPageId: number | null,
  error: unknown,
  prefix: string,
): Promise<void> {
  let msg = errorMessage(error)
  if (msg === 'Failed to fetch') {
    msg = '后端未启动或网络异常，请检查后端是否在运行'
  }
  patchRecognitionPage(target.pageId, {
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
  clearLiveRecognitionPage(target.pageId)
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
      const updated = await historyApi.updatePage(historyPageId, {
        musicxml_file_id: result.musicxml_file_id,
        jianpu_text: result.jianpu_text,
        ocr_text: result.ocr_text,
        svg_file_id: result.svg_file_id,
        start_measure_number: result.start_measure_number,
        status: result.status,
        error_message: result.error_message,
      })
      syncStoreFromHistoryPage(target.pageId, updated)
      notifyHistoryPagePatched(historyPagePatchFromPage(updated))
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
      const createdPage = created.pages[0]
      if (createdPage) {
        syncStoreFromHistoryPage(target.pageId, createdPage)
        notifyHistoryPagePatched(historyPagePatchFromPage(createdPage))
      }
      notifyHistoryUpdated()
    }
  } catch (error: unknown) {
    log.addLog(`保存后台历史结果失败：${errorMessage(error)}`, 'warn')
  }
}

function syncStoreFromHistoryPage(pageId: string, page: HistoryPage): void {
  const options = parseWaitingMeasureOptions(page.error_message)
  const patch = {
    historyPageId: page.id,
    musicxmlFileId: page.musicxml_file_id,
    jianpuText: page.jianpu_text,
    ocrText: page.ocr_text,
    svgFileId: page.svg_file_id,
    startMeasureNumber: page.start_measure_number,
    status: page.status as TaskPageStatus,
    progressPercent: page.status === 'processing' ? 99 : 100,
    progressMessage: page.status === 'waiting'
      ? '等待选择起始小节号'
      : page.status === 'completed'
        ? '识别完成'
        : page.status === 'processing'
          ? (page.error_message || '正在重新渲染')
          : page.error_message,
    measureNumberOptions: page.status === 'waiting' ? options : [],
    errorMessage: page.error_message,
    ...liveRecognitionTaskPatch(page.id, page.status),
  }
  if (!store.patchPageById(pageId, patch)) {
    store.patchPageByHistoryPageId(page.id, patch)
  }
}

function historyPagePatchFromPage(page: HistoryPage): HistoryPagePatchDetail {
  return {
    id: page.id,
    patch: {
      musicxml_file_id: page.musicxml_file_id,
      jianpu_text: page.jianpu_text,
      ocr_text: page.ocr_text,
      svg_file_id: page.svg_file_id,
      start_measure_number: page.start_measure_number,
      status: page.status,
      error_message: page.error_message,
    },
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

function aiMeasureOptions(response: AiTranscribeResponse): number[] {
  const values = uniquePositiveNumbers(
    response.pages.flatMap((page) => page.measure_number_candidates || []),
  )
  return values.length ? values : [1]
}

function aiPageMeasureOptions(page: AiTranscribedPage, fallback: number[]): number[] {
  const values = uniquePositiveNumbers(page.measure_number_candidates || [])
  return values.length ? values : fallback
}

function uniquePositiveNumbers(values: number[]): number[] {
  const result: number[] = []
  for (const value of values) {
    if (!Number.isFinite(value) || value < 1) continue
    const rounded = Math.round(value)
    if (!result.includes(rounded)) result.push(rounded)
  }
  return result
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

function failedMeasureSelectionMessage(options: number[], msg: string): string {
  const prefix = options.length ? `${waitingMeasureMessage(options)}；` : ''
  return `${prefix}选择小节号失败：${msg}`
}

function parseWaitingMeasureOptions(messageText: string): number[] {
  const match = messageText.match(/等待选择起始小节号[:：]\s*([0-9\s、,，]+)/)
  if (!match) return []
  const optionsText = match[1] ?? ''
  return Array.from(optionsText.matchAll(/\d+/g), (valueMatch) => Number(valueMatch[0]))
    .filter((value) => Number.isFinite(value) && value > 0)
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
  width: 100%;
  height: 100%;
  padding: 0 24px 8px;
}

.rv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.rv-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.rv-header p {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 0;
}

/* ── Dashboard Grid ── */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(420px, 1fr));
  grid-template-rows: minmax(280px, auto) minmax(0, 1fr);
  gap: 24px;
  flex: 1;
  min-height: 0;
  align-items: stretch;
}

.dashboard-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.card-recognition,
.card-stats {
  min-height: 280px;
  overflow: visible;
}

.card-uploads,
.card-activity {
  min-height: 0;
  overflow: hidden;
}

.preprocess-inline {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 0 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-base);
  color: var(--text-secondary);
  font-size: 12px;
  flex-shrink: 1;
  min-width: 0;
  max-width: 100%;
}

.preprocess-label {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.preprocess-inline .n-input-number {
  min-width: 80px;
  max-width: 110px;
  flex: 1 1 auto;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  min-width: 0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.card-title :deep(.n-icon) {
  color: var(--accent);
  flex-shrink: 0;
}

.card-header-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  flex-shrink: 0;
  min-width: 0;
}

.batch-select {
  width: 160px;
  max-width: 100%;
  min-width: 0;
}

.batch-select :deep(.n-base-selection) {
  min-width: 0;
}

.batch-select :deep(.n-base-selection-label) {
  padding-left: 6px;
  padding-right: 6px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: visible;
}

.card-recognition .card-body {
  flex: 0 0 auto;
}

.card-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.card-recognition .card-footer {
  margin-top: auto;
  justify-content: flex-start;
}

.card-recognition .card-footer .preprocess-inline {
  margin-left: auto;
}

@media (max-width: 920px) {
  .card-recognition .card-footer {
    gap: 8px;
  }

  .card-recognition .card-footer .preprocess-inline {
    margin-left: 0;
    width: 100%;
    justify-content: flex-end;
  }
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
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

.rv-waiting-banner {
  padding: 8px 12px;
  background: var(--accent-light);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.ai-switch {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-base);
  color: var(--text-secondary);
  font-size: 12px;
}

.selection-count {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  border: 1px solid var(--accent-light);
  border-radius: var(--radius-sm);
  background: var(--accent-light);
  color: var(--accent);
  font-size: 12px;
  font-weight: 500;
}

.stats-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
  justify-content: center;
  min-height: 0;
  overflow: visible;
}

.stats-ring-wrap {
  display: flex;
  align-items: center;
  gap: 18px;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: visible;
  justify-content: flex-start;
}

.stats-ring {
  position: relative;
  width: 76px;
  height: 76px;
  flex-shrink: 0;
}

.stats-ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
  display: block;
}

.ring-bg {
  fill: none;
  stroke: var(--border);
  stroke-width: 3;
}

.ring-segment {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.4s ease;
}

.ring-completed { stroke: var(--success); }
.ring-processing { stroke: var(--warning); }
.ring-failed { stroke: var(--danger); }

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ring-total {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.ring-label {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.stats-legend {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-width: 0;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-completed { background: var(--success); }
.dot-processing { background: var(--warning); }
.dot-failed { background: var(--danger); }
.dot-waiting { background: #868e96; }

.legend-text {
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-value {
  color: var(--text-primary);
  font-weight: 600;
  min-width: 28px;
  text-align: right;
}

.stats-mini-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-self: stretch;
  flex-shrink: 0;
}

.mini-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 48px;
}

.mini-card-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.mini-card-label {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.2;
}

/* ── Uploads ── */
.uploads-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-content: flex-start;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.uploads-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--text-tertiary);
  font-size: 14px;
  flex: 1;
  justify-content: center;
}

.empty-icon {
  color: var(--border);
}

.upload-card {
  position: relative;
  cursor: pointer;
  border-radius: var(--radius-md);
  border: 1.5px solid var(--border);
  background: var(--bg-base);
  padding: 12px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
  min-width: 0;
}

.upload-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.upload-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.upload-card.selected {
  border-color: var(--accent);
  background: var(--accent-light);
}

.upload-card.processing {
  border-color: var(--warning);
}

.upload-card.waiting {
  border-color: var(--warning);
}

.upload-card.failed {
  border-color: var(--danger);
}

.upload-selected-mark {
  position: absolute;
  top: 4px;
  left: 4px;
  z-index: 2;
  color: var(--accent);
  background: var(--bg-base);
  border-radius: 999px;
}

.upload-del {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: var(--bg-elevated);
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

.upload-card:hover .upload-del {
  opacity: 1;
}

.upload-del:hover {
  background: var(--danger);
  color: #fff;
}

.upload-del:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.upload-reupload {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: filter 0.12s ease;
  z-index: 2;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.upload-reupload:hover {
  filter: brightness(0.9);
}

.upload-waiting-action {
  position: absolute;
  top: 4px;
  right: 4px;
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

.upload-waiting-action:hover {
  filter: brightness(0.96);
}

.upload-thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--radius-sm);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-surface);
}

.upload-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.upload-icon {
  color: var(--text-tertiary);
}

.upload-info {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.upload-name {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.upload-status {
  font-size: 12px;
  color: var(--text-tertiary);
}

.upload-status.completed { color: var(--success); }
.upload-status.failed { color: var(--danger); }
.upload-status.processing { color: var(--warning); }
.upload-status.waiting { color: var(--warning); }

.upload-mini-progress {
  height: 3px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--bg-surface);
}

.upload-mini-progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--warning);
  transition: width 0.2s ease;
}

/* ── Activity ── */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1;
  overflow-y: auto;
  padding-right: 4px;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 8px 0;
}

.activity-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.activity-icon.success {
  background: rgba(64, 192, 87, 0.12);
  color: var(--success);
}

.activity-icon.error {
  background: rgba(250, 82, 82, 0.12);
  color: var(--danger);
}

.activity-icon.warn {
  background: rgba(250, 176, 5, 0.12);
  color: var(--warning);
}

.activity-icon.info {
  background: var(--accent-light);
  color: var(--accent);
}

.activity-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  flex: 1;
}

.activity-name {
  font-size: 15px;
  color: var(--text-secondary);
  word-break: break-word;
  line-height: 1.5;
}

.activity-time {
  font-size: 13px;
  color: var(--text-tertiary);
}

.activity-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: var(--text-tertiary);
  font-size: 15px;
  flex: 1;
}

@media (max-height: 840px) and (min-width: 1181px) {
  .dashboard-grid {
    grid-template-rows: minmax(260px, auto) minmax(0, 1fr);
    gap: 18px;
  }

  .dashboard-card {
    padding: 20px 24px;
    gap: 16px;
  }

  .card-recognition,
  .card-stats {
    min-height: 260px;
  }
}

@media (max-width: 1180px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .dashboard-card {
    height: auto;
  }

  .card-recognition,
  .card-stats {
    min-height: 260px;
  }

  .card-uploads,
  .card-activity {
    min-height: 420px;
  }
}

@media (max-width: 720px) {
  .recognize-view {
    padding: 0 12px 8px;
  }

  .dashboard-card {
    padding: 18px;
  }

  .card-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .card-header-right {
    width: 100%;
    justify-content: flex-start;
  }

  .stats-ring-wrap {
    flex-wrap: wrap;
  }

  .stats-mini-cards {
    grid-template-columns: 1fr;
  }

  .uploads-list {
    grid-template-columns: 1fr;
  }
}
</style>
