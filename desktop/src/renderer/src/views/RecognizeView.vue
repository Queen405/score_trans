<template>
  <div class="recognize-view">
    <div class="rv-header">
      <div class="rv-title">
        <h2>智能识别</h2>
      </div>
      <span class="rv-header-text">欢迎加入吉林大学民乐团</span>
    </div>

    <div
      class="dashboard-grid"
      :class="{ 'dashboard-grid--busy': store.activePageTaskCount }"
    >
      <!-- 智能识别 -->
      <div class="dashboard-card card-recognition">
        <div class="card-header">
          <div class="card-title">
            <n-icon size="18">
              <ScanOutline />
            </n-icon>
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
            <div
              v-if="store.pageCount"
              class="page-nav"
            >
              <n-button
                size="small"
                quaternary
                :disabled="!store.canPrevPage"
                @click="store.prevPage()"
              >
                <template #icon>
                  <n-icon><ChevronBackOutline /></n-icon>
                </template>
              </n-button>
              <span class="page-indicator">{{ currentBatchLocalIndex + 1 }} / {{ store.pageCount }}</span>
              <n-button
                size="small"
                quaternary
                :disabled="!store.canNextPage"
                @click="store.nextPage()"
              >
                <template #icon>
                  <n-icon><ChevronForwardOutline /></n-icon>
                </template>
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
        </div>
        <div class="card-footer">
          <n-button
            type="primary"
            size="small"
            :loading="recognizeButtonLoading"
            :disabled="recognizeButtonDisabled"
            @click="recognize"
          >
            <template #icon>
              <n-icon><ScanOutline /></n-icon>
            </template>
            {{ recognizeButtonText }}
          </n-button>
          <n-button
            size="small"
            :loading="store.activePageTaskCount > 0"
            :disabled="!pendingRecognizableCount"
            secondary
            @click="recognizeAllPages"
          >
            <template #icon>
              <n-icon><FlashOutline /></n-icon>
            </template>
            批量识别全部
          </n-button>
          <div class="ai-switch">
            <span>AI 视觉识别</span>
            <n-switch
              v-model:value="aiVisionEnabled"
              size="small"
            />
          </div>
          <div class="instrument-select">
            <span>乐器模式</span>
            <n-select
              v-model:value="instrumentProfile"
              :options="instrumentOptions"
              size="small"
              class="instrument-select-control"
            />
          </div>
          <span
            v-if="selectedPageCount"
            class="selection-count"
          >已选 {{ selectedPageCount }}</span>
        </div>
      </div>

      <!-- 历史记录快速入口 -->
      <div class="dashboard-card card-stats">
        <div class="card-title">
          <n-icon size="18">
            <TimeOutline />
          </n-icon>
          <span>历史记录</span>
        </div>
        <div class="card-stats-scroll">
          <HistoryQuickEntry />
        </div>
      </div>

      <!-- 最近上传 -->
      <div class="dashboard-card card-uploads">
        <div class="card-title">
          最近上传
        </div>
        <div
          v-if="store.currentBatchPages.length"
          class="uploads-list"
        >
          <div
            v-for="page in store.currentBatchPages"
            :key="page.id"
            :class="['upload-card', page.status, {
              active: page.id === store.currentPage?.id,
              selected: isPageSelected(page.id),
            }]"
            @click="handlePageCardClick(page)"
          >
            <n-icon
              v-if="isPageSelected(page.id)"
              size="14"
              class="upload-selected-mark"
            >
              <CheckmarkCircleOutline />
            </n-icon>
            <button
              v-if="page.status === 'failed' && !page.inputFileId"
              class="upload-reupload"
              type="button"
              title="重新上传"
              @click.stop="reuploadForPage(page)"
            >
              <n-icon size="12">
                <CloudUploadOutline />
              </n-icon>
            </button>
            <button
              v-else
              class="upload-del"
              type="button"
              :disabled="page.status === 'processing'"
              @click.stop="removePageById(page.id)"
            >
              <n-icon size="12">
                <CloseOutline />
              </n-icon>
            </button>
            <div class="upload-thumb">
              <img
                v-if="props.active && isPreviewable(page.inputFileName)"
                :src="previewUrl(page.inputFileId)"
                :alt="page.inputFileName"
              >
              <n-icon
                v-else
                size="24"
                class="upload-icon"
              >
                <DocumentOutline />
              </n-icon>
            </div>
            <div class="upload-info">
              <span class="upload-name">{{ page.inputFileName }}</span>
              <span :class="['upload-status', page.status]">{{ statusText(page) }}</span>
            </div>
            <div
              v-if="page.status === 'processing'"
              class="upload-mini-progress"
            >
              <span :style="{ width: `${Math.max(4, page.progressPercent)}%` }" />
            </div>
          </div>
        </div>
        <div
          v-else
          class="uploads-empty"
        >
          <n-icon
            size="32"
            class="empty-icon"
          >
            <CloudUploadOutline />
          </n-icon>
          <span>暂无上传文件</span>
        </div>
      </div>

      <!-- 处理效率仪表盘 -->
      <div class="dashboard-card card-activity">
        <div class="card-title">
          <n-icon size="18">
            <BarChartOutline />
          </n-icon>
          <span>处理效率</span>
        </div>
        <EfficiencyDashboard />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useLogStore } from '../stores/log'
import { useSettingsStore } from '../stores/settings'
import { pipelineApi } from '../api/pipeline'
import { usePublicationRender } from '../composables/usePublicationRender'
import { aiApi } from '../api/ai'
import { tasksApi } from '../api/tasks'
import { historyApi } from '../api/history'
import { filesApi } from '../api/files'
import { notationApi } from '../api/notation'
import { fetchFileBlob, requireData } from '../api/client'
import { isRenderAborted } from '../utils/renderAbort'
import type {
  AiTranscribeResponse,
  AiTranscribedPage,
  HistoryPage,
  InstrumentProfile,
  InstrumentProfileCatalog,
  PipelineResponse,
  SSEProgressEvent,
} from '../models/types'
import type { TaskPage, TaskPageStatus } from '../stores/workspace'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { reconcileTextAnchors } from '../utils/textAnchorTracking'
import { hashJianpuText } from '../utils/jianpuTextState'
import {
  composeJianpuPageText,
  ensureRecognizedPageTempoHeader,
  ensureRecognizedTempoHeader,
} from '../utils/jianpuPageSections'
import {
  buildBatchRenderRequests,
  renderResponsePageOcrTexts,
} from '../utils/batchRender'
import {
  buildHistoryBatchSnapshot,
  isRecognitionBatchReadyForRender,
  recognitionBatchPagesForPage,
} from '../utils/recognitionHistory'
import { notifyHistoryPagePatched, notifyHistoryUpdated } from '../utils/historyEvents'
import { historyPagePatchFromPage } from '../utils/historyPageState'
import {
  clearLiveRecognitionPage,
  getLiveRecognitionHistoryPageId,
  liveRecognitionTaskPatch,
  registerLiveRecognitionPage,
  updateLiveRecognitionPage,
} from '../utils/liveRecognitionState'
import { useFileUpload } from '../composables/useFileUpload'
import FileUploader from '../components/FileUploader.vue'
import HistoryQuickEntry from '../components/HistoryQuickEntry.vue'
import EfficiencyDashboard from '../components/EfficiencyDashboard.vue'
import {
  ScanOutline,
  FlashOutline,
  CloseOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CheckmarkCircleOutline,
  CloudUploadOutline,
  DocumentOutline,
  TimeOutline,
  BarChartOutline,
} from '@vicons/ionicons5'
import { NButton, NIcon, NProgress, NSelect, NSwitch, useMessage } from 'naive-ui'

type RecognitionMode = 'omr' | 'ai'

interface RecognitionTarget {
  pageId: string
  inputFileName: string
  inputFileId: string
  instrumentProfile: InstrumentProfile
}

interface PageResult {
  input_file_name: string
  input_file_id: string
  musicxml_file_id: string
  jianpu_text: string
  ocr_text: string
  svg_file_id: string
  overlay_svg_file_id: string
  overlay_file_id?: string
  source_map_file_id?: string
  text_hash?: string
  text_anchors?: PipelineResponse['text_anchors']
  text_anchor_baseline_text?: string
  text_anchor_baseline_anchors?: PipelineResponse['text_anchors']
  text_attachments?: PipelineResponse['text_attachments']
  status: string
  error_message: string
  omr_file_id?: string
  musicxml_text?: string
}

const store = useWorkspaceStore()
const publicationRender = usePublicationRender()
const log = useLogStore()
const settings = useSettingsStore()
const message = useMessage()
const aiVisionEnabled = ref(false)
const instrumentProfile = ref<InstrumentProfile>('general')
const instrumentCatalogs = ref<InstrumentProfileCatalog[]>([])
const selectedPageIds = ref<Set<string>>(new Set())
const reupload = useFileUpload()
const batchRenderInFlight = new Map<string, Promise<void>>()
const ownedTaskIds = new Set<string>()
const resumingTaskIds = new Set<string>()
const recognitionWaitControllers = new Set<AbortController>()
const ownedLiveRecognitionPageIds = new Set<string>()
let recognitionUnmounted = false

function registerOwnedLiveRecognitionPage(pageId: string, historyPageId: number | null): void {
  registerLiveRecognitionPage(pageId, historyPageId)
  if (historyPageId) ownedLiveRecognitionPageIds.add(pageId)
}

function clearOwnedLiveRecognitionPage(pageId: string): void {
  ownedLiveRecognitionPageIds.delete(pageId)
  clearLiveRecognitionPage(pageId)
}

const instrumentOptions = computed(() => {
  const profiles = instrumentCatalogs.value.length
    ? instrumentCatalogs.value
    : [
        { id: 'general', name: '普通' },
        { id: 'erhu', name: '二胡' },
        { id: 'ruan', name: '阮' },
        { id: 'guzheng', name: '古筝' },
      ]
  return profiles.map((profile) => ({
    label: profile.name,
    value: profile.id,
  }))
})

onMounted(async () => {
  try {
    instrumentCatalogs.value = await requireData(notationApi.listInstrumentProfiles())
  } catch (error: unknown) {
    log.addLog(`加载乐器模式失败：${errorMessage(error)}`, 'warn')
  }
})

const props = withDefaults(defineProps<{
  active?: boolean
}>(), {
  active: true,
})

const previewUrls = ref<Record<string, string>>({})

function previewUrl(fileId: string): string {
  return previewUrls.value[fileId] ?? ''
}

function revokePreviewUrls(): void {
  for (const url of Object.values(previewUrls.value)) {
    URL.revokeObjectURL(url)
  }
  previewUrls.value = {}
}

watch(
  () => props.active
    ? [...new Set(
      store.currentBatchPages
        .filter((page) => isPreviewable(page.inputFileName))
        .map((page) => page.inputFileId),
    )].join('|')
    : '',
  async (joinedFileIds, _previous, onCleanup) => {
    const controller = new AbortController()
    let active = true
    onCleanup(() => {
      active = false
      controller.abort()
    })
    revokePreviewUrls()
    if (!joinedFileIds) return

    const fileIds = joinedFileIds.split('|')
    const results = await Promise.all(
      fileIds.map(async (fileId) => ({
        fileId,
        result: await fetchFileBlob(fileId, controller.signal),
      })),
    )
    if (!active) return

    const urls: Record<string, string> = {}
    for (const { fileId, result } of results) {
      if (!result.error) urls[fileId] = URL.createObjectURL(result.data)
    }
    previewUrls.value = urls
  },
  { immediate: true },
)

onUnmounted(revokePreviewUrls)

onUnmounted(() => {
  recognitionUnmounted = true
  for (const controller of recognitionWaitControllers) controller.abort()
  recognitionWaitControllers.clear()
  for (const pageId of ownedLiveRecognitionPageIds) clearLiveRecognitionPage(pageId)
  ownedLiveRecognitionPageIds.clear()
})

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

watch(
  () => store.currentBatchPages
    .map((page) => `${page.id}:${page.status}:${page.taskId}`)
    .join('|'),
  () => {
    void resumeInterruptedRecognitionTasks()
  },
  { immediate: true },
)

watch(
  () => store.jianpuText,
  (text) => {
    const detected = instrumentProfileFromText(text)
    if (detected) instrumentProfile.value = detected
  },
  { immediate: true },
)

function isPreviewable(fileName: string): boolean {
  return /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(fileName)
}

function isStartablePage(page: TaskPage): boolean {
  return !!page.inputFileId && page.status !== 'processing'
}

function statusText(page: TaskPage): string {
  if (page.status === 'processing') {
    return page.progressPercent > 0 ? `${Math.round(page.progressPercent)}%` : '处理中'
  }
  if (page.status === 'failed' && !page.inputFileId) {
    return '需重新上传'
  }
  const map: Record<string, string> = {
    completed: '完成',
    failed: '失败',
    pending: '待处理',
    unrecognized: '未识别',
  }
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

async function recognize(): Promise<void> {
  const targets = recognizeTargetPages.value.map((page) => targetFromPage(page, { resetInstrumentProfile: true }))
  if (!targets.length) return
  await submitRecognitionTargets(targets, aiVisionEnabled.value ? 'ai' : 'omr')
}

async function recognizeAllPages(): Promise<void> {
  const targets = store.currentBatchPages
    .filter((page) => isStartablePage(page))
    .map((page) => targetFromPage(page, { resetInstrumentProfile: true }))
  if (!targets.length) return
  await submitRecognitionTargets(targets, aiVisionEnabled.value ? 'ai' : 'omr')
}

function targetFromPage(page: TaskPage, options: { resetInstrumentProfile?: boolean } = {}): RecognitionTarget {
  // Prefer originalFileId for re-recognition if the input temp file was cleaned up
  const fileId = page.originalFileId || page.inputFileId
  const savedProfile = instrumentProfileFromText(page.jianpuText)
  return {
    pageId: page.id,
    inputFileName: page.inputFileName,
    inputFileId: fileId,
    instrumentProfile: options.resetInstrumentProfile
      ? instrumentProfile.value
      : (savedProfile ?? instrumentProfile.value),
  }
}

function instrumentProfileFromText(text: string): InstrumentProfile | null {
  const match = text.match(/^\s*instrument\s*=\s*(general|erhu|ruan|zhongruan|guzheng)\s*$/m)
  if (match?.[1] === 'zhongruan') return 'ruan'
  return (match?.[1] as InstrumentProfile | undefined) ?? null
}

async function submitRecognitionTargets(targets: RecognitionTarget[], mode: RecognitionMode): Promise<void> {
  // Check file existence before starting recognition
  const fileIds = targets.map((t) => t.inputFileId).filter(Boolean)
  if (fileIds.length) {
    try {
      const exists = await requireData(filesApi.existsMany(fileIds))
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
  let history: PreparedHistory
  try {
    history = await prepareHistory(targets)
  } catch (error: unknown) {
    const detail = errorMessage(error)
    log.addError(`创建识别历史失败：${detail}`)
    message.error(`无法创建完整历史记录，识别未开始：${detail}`)
    return
  }
  if (hasUnsealedPage) store.sealCurrentBatch()
  const historyPageIds = history.pageIds
  await clearBatchRenderPagesForTargets(targets, {
    preserveJianpuText: true,
  })

  // Update existing history pages to 'processing' for re-recognition
  try {
    for (const target of targets) {
      const historyPageId = historyPageIds.get(target.pageId)
      if (!historyPageId) {
        throw new Error(`页面 ${target.inputFileName} 缺少历史记录编号`)
      }
      registerOwnedLiveRecognitionPage(target.pageId, historyPageId)
      patchRecognitionPage(target.pageId, {
        historyPageId,
      })
      if (!history.created) {
        await requireData(historyApi.updatePage(historyPageId, {
          status: 'processing',
          error_message: '',
        }))
        notifyHistoryPagePatched({
          id: historyPageId,
          patch: {
            status: 'processing',
            error_message: '',
          },
        })
      }
    }
  } catch (error: unknown) {
    for (const target of targets) {
      clearOwnedLiveRecognitionPage(target.pageId)
    }
    const detail = errorMessage(error)
    log.addError(`更新识别历史状态失败：${detail}`)
    message.error(`无法更新历史状态，识别未开始：${detail}`)
    return
  }

  const label = mode === 'ai' ? 'AI 视觉识别' : 'OMR 识别'

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

interface PreparedHistory {
  pageIds: Map<string, number>
  created: boolean
}

async function prepareHistory(targets: RecognitionTarget[]): Promise<PreparedHistory> {
  const pageIds = new Map<string, number>()
  // Reuse existing historyPageId for re-recognition
  for (const target of targets) {
    const page = store.pages.find((p) => p.id === target.pageId)
    if (page?.historyPageId) {
      pageIds.set(target.pageId, page.historyPageId)
    }
  }
  if (pageIds.size === targets.length) {
    return { pageIds, created: false }
  }
  if (pageIds.size) {
    throw new Error('当前批次历史记录不完整，请重新上传后再识别')
  }

  const firstTarget = targets[0]
  if (!firstTarget) throw new Error('没有可识别的页面')
  const batchPages = batchPagesForPage(firstTarget.pageId)
  if (!batchPages.length) throw new Error('找不到待建档的源页面')
  const batchId = batchPages[0]?.batchId
  if (
    !batchId
    || targets.some((target) => !batchPages.some((page) => page.id === target.pageId))
    || batchPages.some((page) => page.historyPageId !== null)
  ) {
    throw new Error('待识别页面不属于同一个未建档批次')
  }

  const selectedPageIds = new Set(targets.map((target) => target.pageId))
  const snapshot = buildHistoryBatchSnapshot(batchPages, selectedPageIds)
  const batchJianpuText = composeJianpuPageText(batchPages)
  const created = await requireData(historyApi.create({
    pages: snapshot.pages,
    jianpu_text: batchJianpuText,
  }))
  if (created.pages.length !== batchPages.length) {
    throw new Error(`历史页数量不一致：期望 ${batchPages.length}，实际 ${created.pages.length}`)
  }

  created.pages.forEach((historyPage, index) => {
    const sourcePage = batchPages[index]
    if (!sourcePage) return
    const selected = selectedPageIds.has(sourcePage.id)
    store.patchPageById(sourcePage.id, {
      historyPageId: historyPage.id,
      historyBatchId: created.id,
      status: selected ? 'processing' : 'unrecognized',
      errorMessage: '',
    })
    if (selected) pageIds.set(sourcePage.id, historyPage.id)
  })
  store.setBatchJianpuText(batchJianpuText, false, batchId)
  notifyHistoryUpdated()
  return { pageIds, created: true }
}

async function runPipelineTarget(target: RecognitionTarget, historyPageId: number | null): Promise<void> {
  markPageProcessing(target, '读取输入文件', 3)
  let submittedTaskId = ''
  try {
    markPageProcessing(target, '提交 OMR 后台任务', 8)

    let submitted: { task_id: string }
    if (target.inputFileId) {
      // Submit directly by file_id — no need to download and re-upload
      submitted = await requireData(pipelineApi.runByFileId({
        file_id: target.inputFileId,
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        instrument_profile: target.instrumentProfile,
        measure_number_mode: settings.measureNumberMode,
        ...settings.jianpuLayoutRequest,
      }))
    } else {
      throw new Error('无输入文件 ID，请重新上传图片')
    }
    submittedTaskId = submitted.task_id
    ownedTaskIds.add(submittedTaskId)
    patchRecognitionPage(target.pageId, { taskId: submitted.task_id })
    updateLiveRecognitionPage(target.pageId, { taskId: submitted.task_id })
    await persistRecognitionTaskId(target.pageId, historyPageId, submitted.task_id)

    const result = await waitForTaskResult(submitted.task_id, target.pageId)
    if (!isPipelineResponse(result)) {
      throw new Error('后台任务返回了无法识别的 OMR 结果格式')
    }
    await applyPipelineResult(target, result, historyPageId)
  } catch (error: unknown) {
    if (recognitionUnmounted) return
    await failTarget(target, historyPageId, error, '识别失败')
  } finally {
    if (submittedTaskId) ownedTaskIds.delete(submittedTaskId)
  }
}

async function runAiTarget(target: RecognitionTarget, historyPageId: number | null): Promise<void> {
  markPageProcessing(target, '提交 AI 视觉识别任务', 5)
  let submittedTaskId = ''
  try {
    const submitted = await requireData(aiApi.transcribe({
      file_id: target.inputFileId,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
      instrument_profile: target.instrumentProfile,
      normalize: true,
    }))
    submittedTaskId = submitted.task_id
    ownedTaskIds.add(submittedTaskId)
    patchRecognitionPage(target.pageId, { taskId: submitted.task_id })
    updateLiveRecognitionPage(target.pageId, { taskId: submitted.task_id })
    await persistRecognitionTaskId(target.pageId, historyPageId, submitted.task_id)

    const response = await waitForTaskResult(submitted.task_id, target.pageId)
    if (!isAiTranscribeResponse(response)) {
      throw new Error('后台任务返回了无法识别的 AI 结果格式')
    }
    if (!response.pages.length) throw new Error('AI 未返回任何页面')

    const warnings = collectAiWarnings(response.pages, response.warnings)
    await applyAiResult(target, response, historyPageId, warnings)
  } catch (error: unknown) {
    if (recognitionUnmounted) return
    await failTarget(target, historyPageId, error, 'AI 转写失败')
  } finally {
    if (submittedTaskId) ownedTaskIds.delete(submittedTaskId)
  }
}

async function waitForTaskResult(taskId: string, pageId: string): Promise<unknown> {
  const controller = new AbortController()
  recognitionWaitControllers.add(controller)
  let completed: SSEProgressEvent
  try {
    completed = await requireData(tasksApi.stream(taskId, (event) => {
      updatePageProgress(pageId, event)
    }, controller.signal))
  } finally {
    recognitionWaitControllers.delete(controller)
  }
  if (!completed.result) {
    throw new Error('任务完成但没有返回结果')
  }
  return completed.result
}

async function persistRecognitionTaskId(
  pageId: string,
  historyPageId: number | null,
  taskId: string,
): Promise<void> {
  if (!historyPageId) return
  try {
    await requireData(historyApi.updatePage(historyPageId, {
      task_id: taskId,
      status: 'processing',
      error_message: '',
    }))
    notifyHistoryPagePatched({
      id: historyPageId,
      patch: {
        task_id: taskId,
        status: 'processing',
        error_message: '',
      },
    })
  } catch (error: unknown) {
    log.addLog(`保存后台任务编号失败：${errorMessage(error)}`, 'warn')
    updateLiveRecognitionPage(pageId, { taskId })
  }
}

async function resumeInterruptedRecognitionTasks(): Promise<void> {
  for (const page of store.currentBatchPages) {
    const taskId = page.taskId
    if (
      page.status !== 'processing'
      || !taskId
      || ownedTaskIds.has(taskId)
      || resumingTaskIds.has(taskId)
    ) {
      continue
    }
    resumingTaskIds.add(taskId)
    store.beginBackgroundTask()
    void resumeInterruptedRecognitionTask(page, taskId).finally(() => {
      resumingTaskIds.delete(taskId)
      store.endBackgroundTask()
    })
  }
}

async function resumeInterruptedRecognitionTask(page: TaskPage, taskId: string): Promise<void> {
  const target = targetFromPage(page)
  const historyPageId = page.historyPageId
  if (historyPageId) {
    registerOwnedLiveRecognitionPage(page.id, historyPageId)
    updateLiveRecognitionPage(page.id, { taskId })
  }
  try {
    const result = await waitForTaskResult(taskId, page.id)
    if (isPipelineResponse(result)) {
      await applyPipelineResult(target, result, historyPageId)
      return
    }
    if (isAiTranscribeResponse(result)) {
      if (!result.pages.length) throw new Error('AI 未返回任何页面')
      const warnings = collectAiWarnings(result.pages, result.warnings)
      await applyAiResult(target, result, historyPageId, warnings)
      return
    }
    throw new Error('后台任务返回了无法识别的结果格式')
  } catch (error: unknown) {
    if (recognitionUnmounted) return
    await failTarget(target, historyPageId, error, '恢复后台识别失败')
  }
}

function isPipelineResponse(value: unknown): value is PipelineResponse {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.musicxml_file_id === 'string'
    && typeof record.jianpu_text === 'string'
}

function isAiTranscribeResponse(value: unknown): value is AiTranscribeResponse {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.merged_jianpu_text === 'string' && Array.isArray(record.pages)
}

function patchRecognitionPage(pageId: string, patch: Partial<TaskPage>): void {
  if (store.patchPageById(pageId, patch)) return
  const historyPageId = getLiveRecognitionHistoryPageId(pageId)
  if (historyPageId) {
    store.patchPageByHistoryPageId(historyPageId, patch)
  }
}

function updatePageProgress(pageId: string, event: SSEProgressEvent): void {
  if (event.status === 'completed') return
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
    overlay_svg_file_id: '',
    status: 'failed',
    error_message: msg,
  }, historyPageId)
  await clearBatchRenderPagesForPage(target.pageId)
  clearOwnedLiveRecognitionPage(target.pageId)
  log.addError(`${prefix}：${target.inputFileName}：${msg}`)
  message.error(`${target.inputFileName}：${msg}`)
}

async function persistPageResult(
  target: RecognitionTarget,
  result: PageResult,
  historyPageId: number | null,
): Promise<HistoryPage | null> {
  try {
    if (historyPageId) {
      const updated = await requireData(historyApi.updatePage(historyPageId, {
        task_id: '',
        musicxml_file_id: result.musicxml_file_id,
        jianpu_text: result.jianpu_text,
        ocr_text: result.ocr_text,
        svg_file_id: result.svg_file_id,
        overlay_svg_file_id: result.overlay_svg_file_id,
        overlay_file_id: result.overlay_file_id ?? '',
        source_map_file_id: result.source_map_file_id ?? '',
        text_hash: result.text_hash ?? '',
        text_anchors: result.text_anchors ?? [],
        text_anchor_baseline_text: result.text_anchor_baseline_text,
        text_anchor_baseline_anchors: result.text_anchor_baseline_anchors,
        text_attachments: result.text_attachments,
        status: result.status,
        error_message: result.error_message,
        omr_file_id: result.omr_file_id ?? '',
        original_musicxml: result.musicxml_text ?? '',
        working_musicxml: result.musicxml_text ?? '',
        deleted_source_ids: [],
      }))
      syncStoreFromHistoryPage(target.pageId, updated)
      notifyHistoryPagePatched(historyPagePatchFromPage(updated))
      return updated
    } else {
      const created = await requireData(historyApi.create({
        pages: [{
          input_file_name: result.input_file_name,
          input_file_id: result.input_file_id,
          task_id: '',
          musicxml_file_id: result.musicxml_file_id,
          jianpu_text: result.jianpu_text,
          ocr_text: result.ocr_text,
          svg_file_id: result.svg_file_id,
          overlay_svg_file_id: result.overlay_svg_file_id,
          overlay_file_id: result.overlay_file_id ?? '',
          source_map_file_id: result.source_map_file_id ?? '',
          text_hash: result.text_hash ?? '',
          text_anchors: result.text_anchors ?? [],
          text_anchor_baseline_text: result.text_anchor_baseline_text,
          text_anchor_baseline_anchors: result.text_anchor_baseline_anchors,
          text_attachments: result.text_attachments ?? [],
          status: result.status,
          error_message: result.error_message,
          omr_file_id: result.omr_file_id ?? '',
          original_musicxml: result.musicxml_text ?? '',
          working_musicxml: result.musicxml_text ?? '',
          deleted_source_ids: [],
        }],
      }))
      const pageId = created.pages[0]?.id
      if (pageId) {
        store.patchPageById(target.pageId, {
          historyPageId: pageId,
          historyBatchId: created.id,
        })
      }
      const createdPage = created.pages[0]
      if (createdPage) {
        syncStoreFromHistoryPage(target.pageId, createdPage)
        notifyHistoryPagePatched(historyPagePatchFromPage(createdPage))
      }
      notifyHistoryUpdated()
      return createdPage ?? null
    }
  } catch (error: unknown) {
    log.addLog(`保存后台历史结果失败：${errorMessage(error)}`, 'warn')
    return null
  }
}

function syncStoreFromHistoryPage(pageId: string, page: HistoryPage): void {
  const existing = store.pages.find((entry) => entry.id === pageId)
    ?? store.pages.find((entry) => entry.historyPageId === page.id)
  const hasTextAnchorBaseline = page.text_anchor_baseline_text !== undefined
    && page.text_anchor_baseline_anchors !== undefined
  const patch = {
    historyPageId: page.id,
    taskId: page.task_id || '',
    musicxmlFileId: page.musicxml_file_id,
    jianpuText: page.jianpu_text,
    ocrText: page.ocr_text,
    svgFileId: page.svg_file_id,
    overlayFileId: page.overlay_file_id || page.overlay_svg_file_id || '',
    sourceMapFileId: page.source_map_file_id ?? '',
    textHash: page.text_hash ?? '',
    textAnchors: page.text_anchors ?? [],
    textAnchorBaselineText: hasTextAnchorBaseline
      ? page.text_anchor_baseline_text
      : page.jianpu_text,
    textAnchorBaselineAnchors: hasTextAnchorBaseline
      ? page.text_anchor_baseline_anchors
      : (page.text_anchors ?? []),
    textAttachments: page.text_attachments ?? [],
    svgFileIds: existing?.svgFileIds.length ? existing.svgFileIds : (page.svg_file_id ? [page.svg_file_id] : []),
    historyBatchId: page.batch_id ?? null,
    status: page.status as TaskPageStatus,
    progressPercent: page.status === 'processing' ? 99 : 100,
    progressMessage: page.status === 'completed'
        ? '识别完成'
        : page.status === 'processing'
          ? (page.error_message || '正在重新渲染')
          : page.error_message,
    errorMessage: page.error_message,
    omrFileId: page.omr_file_id ?? '',
    originalMusicxml: page.original_musicxml ?? '',
    workingMusicxml: page.working_musicxml || page.original_musicxml || '',
    deletedSourceIds: page.deleted_source_ids ?? [],
    ...liveRecognitionTaskPatch(page.id, page.status),
  }
  if (!store.patchPageById(pageId, patch)) {
    store.patchPageByHistoryPageId(page.id, patch)
  }
}

async function applyPipelineResult(
  target: RecognitionTarget,
  result: PipelineResponse,
  historyPageId: number | null,
): Promise<void> {
    const split = splitJianpuAndOcr(result.jianpu_text)
    const batchPageIndex = batchPagesForPage(target.pageId)
      .findIndex((page) => page.id === target.pageId)
    const recognizedJianpuText = ensureRecognizedPageTempoHeader(
      split.jianpuText,
      batchPageIndex,
    )
    const warnings = result.warnings ?? []
    let ocrText = returnedPipelineOcrText(result) || split.ocrText
    let svgFileId = result.svg_file_id
    let svgFileIds = renderPageIds(result.render_pages, result.svg_file_id)
    const sourceTextAnchors = result.text_anchors ?? []
    const alignment = reconcileTextAnchors(
      result.jianpu_text,
      recognizedJianpuText,
      sourceTextAnchors,
    )
    const textAnchorBaselineAnchors = alignment.reconciled
      ? alignment.anchors
      : sourceTextAnchors.map((anchor) => ({ ...anchor, valid: false }))
    let textAnchors = textAnchorBaselineAnchors.map((anchor) => ({ ...anchor }))
    const textAttachments = result.text_attachments ?? []
    const textHash = await hashJianpuText(recognizedJianpuText)
    const pageResult: PageResult = {
      input_file_name: target.inputFileName,
      input_file_id: target.inputFileId,
      musicxml_file_id: result.musicxml_file_id,
      jianpu_text: recognizedJianpuText,
      ocr_text: ocrText,
      svg_file_id: svgFileId,
      overlay_svg_file_id: result.overlay_svg_file_id ?? '',
      overlay_file_id: result.overlay_file_id ?? '',
      source_map_file_id: result.source_map_file_id ?? '',
      text_hash: textHash,
      text_anchors: textAnchors,
      text_anchor_baseline_text: recognizedJianpuText,
      text_anchor_baseline_anchors: textAnchorBaselineAnchors,
      text_attachments: textAttachments,
      status: 'completed',
      error_message: warnings.join('；'),
      omr_file_id: result.omr_file_id ?? '',
      musicxml_text: result.musicxml_text ?? '',
    }
    patchRecognitionPage(target.pageId, {
      musicxmlFileId: result.musicxml_file_id,
      musicxmlText: '',
      jianpuText: recognizedJianpuText,
      ocrText,
      jianpuDirty: false,
      svgFileId,
      svgFileIds,
      overlayFileId: result.overlay_file_id || result.overlay_svg_file_id || '',
      sourceMapFileId: result.source_map_file_id ?? '',
      textHash,
      textAnchors,
      textAnchorBaselineText: recognizedJianpuText,
      textAnchorBaselineAnchors,
      textAttachments,
      originalFileName: isPreviewable(target.inputFileName) ? target.inputFileName : '',
      originalFileId: isPreviewable(target.inputFileName) ? target.inputFileId : '',
      taskId: '',
      status: 'completed',
      progressPercent: 100,
      progressMessage: '识别完成',
      errorMessage: warnings.join('；'),
      omrFileId: result.omr_file_id ?? '',
      originalMusicxml: result.musicxml_text ?? '',
      workingMusicxml: result.musicxml_text ?? '',
    })
    await persistPageResult(target, pageResult, historyPageId)
    await syncBatchJianpuTextForPage(target.pageId)
    void maybeRenderCompletedBatchForPage(target.pageId)
    clearOwnedLiveRecognitionPage(target.pageId)
    log.addLog(
      warnings.length
        ? `识别完成，但有 ${warnings.length} 条警告：${target.inputFileName}`
        : `识别完成：${target.inputFileName}`,
      warnings.length ? 'warn' : 'info',
    )
    if (warnings.length) {
      message.warning(warnings.slice(0, 3).join('；'))
    } else {
      message.success(`识别完成：${target.inputFileName}`)
    }
}

async function applyAiResult(
  target: RecognitionTarget,
  response: AiTranscribeResponse,
  historyPageId: number | null,
  warnings: string[],
): Promise<void> {
    const batchPageIndex = batchPagesForPage(target.pageId)
      .findIndex((page) => page.id === target.pageId)
    const mergedJianpuText = ensureRecognizedPageTempoHeader(
      response.merged_jianpu_text,
      batchPageIndex,
    )
    let svgFileId = ''
    let svgFileIds: string[] = []
    patchRecognitionPage(target.pageId, {
      inputFileName: target.inputFileName,
      inputFileId: target.inputFileId,
      originalFileName: target.inputFileName,
      originalFileId: target.inputFileId,
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: mergedJianpuText,
      textAnchors: [],
      textAnchorBaselineText: mergedJianpuText,
      textAnchorBaselineAnchors: [],
      ocrText: '',
      jianpuDirty: false,
      svgFileId,
      svgFileIds,
      taskId: '',
      status: 'completed',
      progressPercent: 100,
      progressMessage: 'AI 转写完成',
      errorMessage: warnings.join('；'),
    })
    const pageResult: PageResult = {
      input_file_name: target.inputFileName,
      input_file_id: target.inputFileId,
      musicxml_file_id: '',
      jianpu_text: mergedJianpuText,
      ocr_text: '',
      svg_file_id: svgFileId,
      overlay_svg_file_id: '',
      text_anchors: [],
      text_anchor_baseline_text: mergedJianpuText,
      text_anchor_baseline_anchors: [],
      status: 'completed',
      error_message: warnings.join('；'),
    }
    await persistPageResult(target, pageResult, historyPageId)
    await syncBatchJianpuTextForPage(target.pageId)
    void maybeRenderCompletedBatchForPage(target.pageId)
    clearOwnedLiveRecognitionPage(target.pageId)
    if (warnings.length) {
      log.addLog(`AI 转写完成：${target.inputFileName}`)
      message.warning(warnings.slice(0, 3).join('；'))
    } else {
      log.addLog(`AI 转写完成：${target.inputFileName}`)
      message.success(`AI 转写完成：${target.inputFileName}`)
    }
}

function collectAiWarnings(pages: AiTranscribedPage[], responseWarnings: string[] | undefined): string[] {
  return [
    ...(responseWarnings ?? []),
    ...pages.flatMap((page) => [...(page.validation_errors ?? []), ...(page.warnings ?? [])]),
  ]
}

function taskProgressText(event: SSEProgressEvent): string {
  if (event.status === 'failed') return event.error || event.message || '任务失败'
  return event.message || event.stage || '处理中'
}

function renderPageIds(pages: PipelineResponse['render_pages'], fallback: string): string[] {
  const ids = (pages ?? []).map((page) => page.svg_file_id).filter(Boolean)
  return ids.length ? ids : (fallback ? [fallback] : [])
}

async function maybeRenderCompletedBatchForPage(pageId: string): Promise<void> {
  const batchPages = batchPagesForPage(pageId)
  if (!batchPages.length) return
  const batchId = batchPages[0]?.batchId
  if (!isRecognitionBatchReadyForRender(batchPages.map((page) => page.status))) {
    store.setBatchRenderPageFileIds([], batchId)
    return
  }
  if (!batchId) return

  const currentRender = batchRenderInFlight.get(batchId)
  if (currentRender) return currentRender

  const render = (async () => {
    await syncBatchJianpuTextForPage(pageId)
    if (store.batchJianpuPendingPageIdsFor(batchId).length) {
      store.setBatchRenderPageFileIds([], batchId)
      return
    }
    const batchText = store.batchJianpuTextFor(batchId)
    const pages = buildBatchRenderRequests(batchPages, { jianpuText: batchText })
      .map((page, index) => ({
        ...page,
        text_anchors: batchPages[index]?.textAnchors ?? [],
      }))
    if (!pages.length) {
      store.setBatchRenderPageFileIds([], batchId)
      return
    }

    try {
      const result = await requireData(publicationRender.batchA4({
        pages,
        source_pages: buildBatchRenderRequests(batchPages, { jianpuText: batchText }),
        render_page_ocr_texts: batchRenderPageOcrTextsForRequest(batchId),
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        instrument_profile: batchPages
          .map((page) => instrumentProfileFromText(page.jianpuText))
          .find((profile): profile is InstrumentProfile => profile !== null)
          ?? instrumentProfile.value,
        measure_number_mode: settings.measureNumberMode,
        initial_measure_number: 1,
        title: '简谱',
        ...settings.jianpuLayoutRequest,
      }))
      const ids = result.pages.map((page) => page.svg_file_id).filter(Boolean)
      const layoutKey = result.pages[0]?.layout_key || settings.jianpuLayoutKey
      store.setBatchRenderPageFileIds(ids, batchId, layoutKey)
      store.setBatchRenderPageOcrTexts(renderResponsePageOcrTexts(result.pages), false, batchId)
      store.markBatchRenderPageOcrClean(batchId)
      const historyBatchId = historyBatchIdForPages(batchPages)
      if (historyBatchId) {
        const batchText = store.batchJianpuTextFor(batchId)
        if (batchText) {
          await requireData(historyApi.updateBatchJianpuText(historyBatchId, { jianpu_text: batchText, source: 'auto' }))
        }
        const updated = await requireData(historyApi.updateRenderState(historyBatchId, {
          render_page_file_ids: ids,
          render_page_ocr_texts: store.batchRenderPageOcrTextsFor(batchId),
          render_output_stale: false,
          render_layout_key: layoutKey,
        }))
        store.setBatchRenderPageFileIds(
          updated.render_page_file_ids ?? [],
          batchId,
          updated.render_layout_key ?? '',
        )
        store.setBatchRenderPageOcrTexts(updated.render_page_ocr_texts || [], false, batchId)
        notifyHistoryUpdated()
      }
    } catch (error: unknown) {
      if (isRenderAborted(error)) return
      log.addLog(`生成连续 A4 简谱失败：${errorMessage(error)}`, 'warn')
    }
  })()
  batchRenderInFlight.set(batchId, render)
  try {
    await render
  } finally {
    if (batchRenderInFlight.get(batchId) === render) {
      batchRenderInFlight.delete(batchId)
    }
  }
}

async function clearBatchRenderPagesForTargets(
  targets: RecognitionTarget[],
  options: { preserveJianpuText?: boolean } = {},
): Promise<void> {
  const batchIds = new Set<string>()
  for (const target of targets) {
    const page = store.pages.find((entry) => entry.id === target.pageId)
    if (page?.batchId) batchIds.add(page.batchId)
  }
  for (const batchId of batchIds) {
    if (!options.preserveJianpuText && !store.isBatchJianpuDirty(batchId)) {
      store.setBatchJianpuText('', false, batchId)
    }
    await clearBatchRenderPages(batchId)
  }
}

async function clearBatchRenderPagesForPage(pageId: string): Promise<void> {
  const page = store.pages.find((entry) => entry.id === pageId)
  if (!page?.batchId) return
  await clearBatchRenderPages(page.batchId)
}

async function clearBatchRenderPages(batchId: string): Promise<void> {
  store.setBatchRenderPageFileIds([], batchId)
  const historyBatchId = historyBatchIdForPages(store.pages.filter((page) => page.batchId === batchId))
  if (!historyBatchId) return
  try {
    await requireData(historyApi.updateRenderState(historyBatchId, {
      render_page_file_ids: [],
      render_page_ocr_texts: store.batchRenderPageOcrTextsFor(batchId),
      render_output_stale: true,
      render_layout_key: '',
    }))
    notifyHistoryUpdated()
  } catch (error: unknown) {
    log.addLog(`清理连续 A4 渲染页失败：${errorMessage(error)}`, 'warn')
  }
}

function batchPagesForPage(pageId: string): TaskPage[] {
  return recognitionBatchPagesForPage(
    store.pages,
    pageId,
    getLiveRecognitionHistoryPageId(pageId),
  )
}

function batchRenderPageOcrTextsForRequest(batchId: string | undefined) {
  if (!batchId) return []
  const entries = store.batchRenderPageOcrTextsFor(batchId)
  if (store.isBatchRenderPageOcrDirty(batchId)) return entries
  return entries.filter((item) => item.ocr_text.trim())
}

function returnedPipelineOcrText(result: PipelineResponse): string {
  return result.ocr_text || result.render_pages?.find((page) => page.ocr_text)?.ocr_text || ''
}

async function syncBatchJianpuTextForPage(pageId: string): Promise<void> {
  const batchPages = batchPagesForPage(pageId)
  const batchId = batchPages[0]?.batchId
  if (!batchId) return
  if (store.isBatchJianpuDirty(batchId)) {
    store.markBatchJianpuPagePending(pageId, batchId)
    return
  }
  const text = ensureRecognizedTempoHeader(composeJianpuPageText(batchPages))
  store.setBatchJianpuText(text, false, batchId)
  const historyBatchId = historyBatchIdForPages(batchPages)
  if (!historyBatchId) return
  try {
    await requireData(historyApi.updateBatchJianpuText(historyBatchId, { jianpu_text: text, source: 'auto' }))
  } catch (error: unknown) {
    log.addLog(`保存批次简谱文本失败：${errorMessage(error)}`, 'warn')
  }
}

function historyBatchIdForPages(batchPages: TaskPage[]): number | null {
  return batchPages.find((page) => page.historyBatchId != null)?.historyBatchId ?? null
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
  justify-content: flex-start;
  gap: 12px;
}

.rv-title {
  display: flex;
  align-items: center;
}

.rv-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.rv-header-text {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  grid-template-rows: auto minmax(0, 1fr);
  gap: 24px;
  flex: 1;
  min-height: 0;
  align-items: stretch;
}

.dashboard-grid--busy {
  grid-template-rows: auto minmax(0, 1fr);
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
}

.card-recognition {
  height: 100%;
  align-self: stretch;
  overflow: hidden;
}

.card-stats {
  height: 100%;
  align-self: stretch;
  overflow: hidden;
}

.card-stats-scroll {
  position: relative;
  flex: 1;
  min-height: 0;
}

.card-stats-scroll :deep(.history-quick) {
  position: absolute;
  inset: 0;
}

.card-uploads,
.card-activity {
  min-height: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  flex-shrink: 0;
  min-width: 0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
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
  margin-left: auto;
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
  min-height: 0;
  overflow-x: hidden;
  overflow-y: visible;
}

.card-recognition .card-body > .upload-container,
.card-recognition .rv-progress,
.card-recognition .rv-waiting-banner {
  flex-shrink: 0;
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
  margin-top: 0;
  justify-content: flex-start;
  padding-top: 6px;
}

.dashboard-grid--busy .card-recognition {
  gap: 6px;
  padding: 18px 24px;
}

.dashboard-grid--busy .card-recognition .card-body {
  gap: 4px;
}

.dashboard-grid--busy .card-recognition .card-footer {
  padding-top: 4px;
}

@media (max-width: 920px) {
  .card-recognition .card-footer {
    gap: 8px;
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

.ai-switch,
.instrument-select {
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

.instrument-select {
  padding-right: 4px;
}

.instrument-select-control {
  width: 92px;
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
.upload-status.unrecognized { color: var(--text-tertiary); }

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

@media (max-height: 840px) and (min-width: 1181px) {
  .dashboard-grid {
    grid-template-rows: auto minmax(0, 1fr);
    gap: 18px;
  }

  .dashboard-grid--busy {
    grid-template-rows: auto minmax(0, 1fr);
  }

  .dashboard-card {
    padding: 20px 24px;
    gap: 12px;
  }

  .card-recognition,
  .card-stats {
    min-height: 260px;
  }

  .dashboard-grid--busy .card-recognition {
    gap: 6px;
    padding: 16px 20px;
  }

  .dashboard-grid--busy .card-recognition .card-body {
    gap: 4px;
  }

  .dashboard-grid--busy .card-recognition .card-footer {
    padding-top: 4px;
  }
}

@media (max-width: 1400px) and (min-width: 1181px) {
  .card-recognition .card-footer {
    flex-wrap: nowrap;
    gap: 6px;
    padding-top: 8px;
  }

  .card-recognition .card-footer :deep(.n-button) {
    padding: 0 6px;
    font-size: 12px;
  }

  .card-recognition .card-footer :deep(.n-button__icon) {
    display: none;
  }

  .card-recognition .ai-switch,
  .card-recognition .instrument-select {
    gap: 4px;
    padding: 0 5px;
    white-space: nowrap;
  }

  .card-recognition .instrument-select {
    padding-right: 2px;
  }

  .card-recognition .instrument-select-control {
    width: 72px;
  }

  .card-recognition .selection-count {
    display: none;
  }
}

@media (max-width: 1180px) {
  .dashboard-grid,
  .dashboard-grid--busy {
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

  .uploads-list {
    grid-template-columns: 1fr;
  }
}
</style>
