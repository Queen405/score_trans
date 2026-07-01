<template>
  <div class="workspace">
    <div :class="['ws-history', { open: historyOpen }]">
      <div class="ws-hist-head">
        <span class="ws-hist-title">历史</span>
        <div class="ws-hist-actions">
          <n-button
            size="tiny"
            quaternary
            :loading="histLoading"
            @click="loadHistory()"
          >
            <template #icon>
              <n-icon size="14">
                <RefreshOutline />
              </n-icon>
            </template>
          </n-button>
          <n-popconfirm
            :show-icon="false"
            @positive-click="handleDeleteAll"
          >
            <template #trigger>
              <n-button
                size="tiny"
                quaternary
                type="error"
                :disabled="!histBatches.length"
              >
                <template #icon>
                  <n-icon size="14">
                    <TrashOutline />
                  </n-icon>
                </template>
              </n-button>
            </template>
            确定删除所有历史记录？
          </n-popconfirm>
        </div>
      </div>
      <div class="ws-hist-body">
        <div
          v-if="!histLoading && !histBatches.length"
          class="hist-empty"
        >
          <span>暂无记录</span>
        </div>
        <div
          v-for="batch in histBatches"
          :key="batch.id"
          class="hist-batch"
        >
          <div
            class="hist-batch-head"
            @click="toggleBatchExpand(batch.id)"
          >
            <span :class="['hist-dot', historyStatusClass(batch.status)]" />
            <span class="hist-batch-name">{{ batch.first_file_name || '未知' }}</span>
            <span
              v-if="batch.page_count > 1"
              class="hist-batch-count"
            >{{ batch.page_count }}页</span>
            <span
              v-if="isWaitingStatus(batch.status)"
              class="hist-waiting-label"
            >待选择</span>
            <n-popconfirm
              :show-icon="false"
              @positive-click="handleDeleteBatch(batch.id)"
            >
              <template #trigger>
                <button
                  class="hist-delete"
                  type="button"
                  title="删除该历史记录"
                  @click.stop
                >
                  <n-icon size="12">
                    <TrashOutline />
                  </n-icon>
                </button>
              </template>
              确定删除这次历史记录？
            </n-popconfirm>
            <n-icon
              size="12"
              class="hist-expand-icon"
              :class="{ rotated: expandedBatchId === batch.id }"
            >
              <ChevronForwardOutline />
            </n-icon>
          </div>
          <div class="hist-batch-meta">
            {{ formatTime(batch.created_at) }}
          </div>
          <div
            v-if="expandedBatchId === batch.id"
            class="hist-pages"
          >
            <div
              v-if="loadingBatchId === batch.id"
              class="hist-loading"
            >
              加载中...
            </div>
            <div
              v-for="(page, pi) in expandedPages"
              :key="page.id"
              :class="['hist-page-item', { 'hist-page-waiting': isWaitingStatus(page.status) }]"
              @click="handleHistoryPageClick(page)"
            >
              <span :class="['hist-dot small', historyStatusClass(page.status)]" />
              <span class="hist-page-name">{{ page.input_file_name || `第${pi + 1}页` }}</span>
              <span
                v-if="isWaitingStatus(page.status)"
                class="hist-waiting-label"
              >待选择</span>
              <span
                v-else-if="page.status === 'unrecognized'"
                class="hist-unrecognized-label"
              >未识别</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="ws-main">
      <div class="ws-toolbar">
        <div class="ws-toolbar-left">
          <button
            class="hist-toggle"
            title="历史记录"
            @click="toggleHistory"
          >
            <n-icon size="16">
              <TimeOutline />
            </n-icon>
          </button>
          <div
            v-if="store.pageCount"
            class="page-nav"
          >
            <n-button
              size="small"
              quaternary
              :disabled="!store.canPrevPage || store.isBusy"
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
              :disabled="!store.canNextPage || store.isBusy"
              @click="store.nextPage()"
            >
              <template #icon>
                <n-icon><ChevronForwardOutline /></n-icon>
              </template>
            </n-button>
          </div>
        </div>
        <div class="ws-toolbar-right">
          <n-button
            size="small"
            :loading="store.isBusy"
            :disabled="!store.hasMusicxml"
            type="primary"
            @click="musicxmlToJianpu"
          >
            重置简谱
          </n-button>
          <n-button
            size="small"
            type="primary"
            :loading="store.isBusy"
            :disabled="!store.hasMusicxml"
            @click="exportScore"
          >
            <template #icon>
              <n-icon><CloudDownloadOutline /></n-icon>
            </template>
            导出
          </n-button>
          <n-select
            v-model:value="exportFormat"
            :options="formatOptions"
            size="small"
            style="width: 96px"
          />
        </div>
      </div>

      <div class="ws-layout">
        <div class="ws-panel ws-left">
          <div class="ws-panel-head">
            <span>原始五线谱</span>
            <span
              v-if="store.originalFileName"
              class="panel-filename"
            >{{ store.originalFileName }}</span>
          </div>
          <div class="ws-panel-body">
            <original-preview
              :file-id="store.originalFileId"
              :file-name="store.originalFileName"
              :overlay-file-id="store.overlayFileId"
            />
          </div>
        </div>

        <div class="ws-panel ws-right">
          <div class="ws-panel-head">
            <span>{{ isViewingFinal ? '最终渲染' : '简谱编辑' }}</span>
            <div class="panel-head-actions">
              <div class="panel-head-meta">
                <span class="meta-label">起始小节</span>
                <n-input-number
                  :value="batchStartMeasureNumber"
                  placeholder="自动"
                  :min="1"
                  clearable
                  size="tiny"
                  style="width: 100px"
                  @update:value="handleStartMeasureChange"
                />
              </div>
              <n-button
                v-if="store.currentBatchJianpuPendingPageIds.length"
                size="tiny"
                type="warning"
                secondary
                @click="mergePendingRecognitionResults"
              >
                <template #icon>
                  <n-icon size="13">
                    <RefreshOutline />
                  </n-icon>
                </template>
                合入识别结果
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :loading="store.isBusy"
                :disabled="store.isBusy || !canSaveCurrentPage"
                @click="saveJianpu"
              >
                保存
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :loading="isRenderingFinal"
                :disabled="store.isBusy || !canRenderCurrentScore"
                @click="toggleFinalView"
              >
                {{ isViewingFinal ? '编辑' : '渲染' }}
              </n-button>
              <div
                v-if="isViewingFinal && finalSvgFileIds.length > 1"
                class="render-page-nav"
              >
                <n-button
                  size="tiny"
                  quaternary
                  :disabled="finalRenderPageIndex <= 0"
                  @click="finalRenderPageIndex--"
                >
                  <template #icon>
                    <n-icon size="12">
                      <ChevronBackOutline />
                    </n-icon>
                  </template>
                </n-button>
                <span>{{ finalRenderPageIndex + 1 }} / {{ finalSvgFileIds.length }}</span>
                <n-button
                  size="tiny"
                  quaternary
                  :disabled="finalRenderPageIndex >= finalSvgFileIds.length - 1"
                  @click="finalRenderPageIndex++"
                >
                  <template #icon>
                    <n-icon size="12">
                      <ChevronForwardOutline />
                    </n-icon>
                  </template>
                </n-button>
              </div>
            </div>
          </div>
          <div class="ws-panel-body">
            <svg-preview
              v-if="isViewingFinal && finalSvgFileId"
              :svg-file-id="finalSvgFileId"
              :ocr-text="finalRenderPageOcrText"
              :current-note-index="currentNoteIndex"
              editable-ocr
              @update:ocr-text="handleOcrTextUpdate"
            />
            <div
              v-else-if="isViewingFinal"
              class="empty-hint"
            >
              <n-icon
                size="32"
                :depth="3"
              >
                <ImageOutline />
              </n-icon>
              <span>暂无渲染</span>
            </div>
            <jianpu-editor
              v-else
              v-model="jianpuText"
              :start-measure-number="batchStartMeasureNumber ?? 1"
              :current-note-index="currentNoteIndex"
              :syntax-highlight="settings.jianpuSyntaxHighlight"
              :error-line="errorLine"
              :flash-line="flashLine"
            />
          </div>
        </div>
      </div>
      <jianpu-player
        :musicxml-file-id="store.musicxmlFileId"
        :jianpu-text="jianpuText"
        @update:current-note-index="currentNoteIndex = $event"
      />
    </div>
    <MeasureNumberPicker
      v-model:show="histPickerShow"
      :options="histPickerOptions"
      @confirm="onHistPickerConfirm"
      @cancel="histPickerShow = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { convertApi } from '../api/convert'
import { renderApi } from '../api/render'
import { downloadBlob, exportApi, svgToJpegBlob, svgToPngBlob } from '../api/export'
import { historyApi } from '../api/history'
import { ApiError, requireData } from '../api/client'
import { filesApi } from '../api/files'
import type {
  HistoryBatchListItem,
  HistoryBatch,
  HistoryPage,
} from '../models/types'
import type { TaskPage } from '../stores/workspace'
import JianpuEditor from '../components/JianpuEditor.vue'
import JianpuPlayer from '../components/JianpuPlayer.vue'
import OriginalPreview from '../components/OriginalPreview.vue'
import SvgPreview from '../components/SvgPreview.vue'
import MeasureNumberPicker from '../components/MeasureNumberPicker.vue'
import { splitJianpuAndOcr } from '../utils/ocrText'
import {
  composeJianpuPageText,
  hasJianpuPageMarkers,
  parseJianpuPageSections,
  replaceJianpuSectionBody,
  updateJianpuPageStart,
} from '../utils/jianpuPageSections'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import { createRequestEpoch } from '../utils/asyncCoordination'
import {
  buildBatchRenderRequests,
  renderPageOcrTextsForRequest,
  renderResponsePageIds,
  renderResponsePageOcrTexts,
} from '../utils/batchRender'
import {
  failedMeasureSelectionMessage,
  historyPageOpenAction,
  historyPagePatchFromPage,
  isPreviewableHistoryFile,
  parseWaitingMeasureOptions,
} from '../utils/historyPageState'
import {
  listenHistoryPagePatched,
  listenHistoryUpdated,
  notifyHistoryPagePatched,
  type HistoryPagePatchDetail,
} from '../utils/historyEvents'
import {
  ImageOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CloudDownloadOutline,
  TimeOutline,
  RefreshOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { NButton, NSelect, NIcon, NPopconfirm, NInputNumber, useMessage } from 'naive-ui'

const store = useWorkspaceStore()
const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const jianpuText = ref(store.currentBatchJianpuText)
const hasJianpuText = computed(() => jianpuText.value.trim().length > 0)
const currentNoteIndex = ref(-1)
const errorLine = ref(-1)
const flashLine = ref(-1)
const canRenderCurrentScore = computed(() => hasJianpuText.value || store.hasMusicxml)
const finalRenderPageOcrText = computed(() =>
  store.currentBatchRenderPageOcrText(finalRenderPageIndex.value),
)
const canSaveCurrentPage = computed(() =>
  hasJianpuText.value
  || store.hasMusicxml
  || !!store.ocrText.trim()
  || !!finalRenderPageOcrText.value.trim()
  || !!store.svgFileId,
)
const isViewingFinal = ref(false)
const isRenderingFinal = ref(false)
const finalSvgFileIds = ref<string[]>(store.currentBatchRenderPageFileIds.length
  ? [...store.currentBatchRenderPageFileIds]
  : currentPageSvgIds())
const finalRenderPageIndex = ref(0)
const finalSvgFileId = computed(() => finalSvgFileIds.value[finalRenderPageIndex.value] ?? '')
const exportFormat = ref('pdf')
const formatOptions = [
  { label: 'PDF', value: 'pdf' },
  { label: 'PNG', value: 'png' },
  { label: 'MIDI', value: 'mid' },
  { label: 'MusicXML', value: 'musicxml' },
]

const historyOpen = ref(false)
const histBatches = ref<HistoryBatchListItem[]>([])
const histLoading = ref(false)
const expandedBatchId = ref<number | null>(null)
const expandedPages = ref<HistoryPage[]>([])
const loadingBatchId = ref<number | null>(null)
const histPickerShow = ref(false)
const histPickerOptions = ref<number[]>([])
const histPickerPage = ref<HistoryPage | null>(null)
let stopHistoryUpdatedListener: (() => void) | null = null
let stopHistoryPagePatchedListener: (() => void) | null = null
let historyListRequestSeq = 0
const historyDetailEpoch = createRequestEpoch()
let restoreCheckSeq = 0
const locallyUpdatingHistoryPageIds = new Set<number>()
const checkingHistoryPageIds = new Set<number>()
const selectingHistoryPageIds = new Set<number>()

const currentBatchLocalIndex = computed(() =>
  store.currentBatchPages.indexOf(store.currentPage!),
)
const batchStartMeasureNumber = computed(() =>
  firstBatchPage()?.startMeasureNumber ?? store.startMeasureNumber ?? null,
)

// Distinguish programmatic text changes (store pushes and their cascading
// auto-formatting in JianpuEditor) from genuine user edits (typing). Only the
// latter should mark the batch as dirty so that recognition results can still
// flow into the editor via syncBatchJianpuTextForPage.
let programmaticUpdate = false

watch(() => store.currentBatchJianpuText, (v) => {
  if (v !== jianpuText.value) {
    programmaticUpdate = true
    jianpuText.value = v
    // Vue 3's nextTick resolves after the entire flush queue — including the
    // cascading auto-formatting watch in JianpuEditor — so the flag stays true
    // long enough to suppress the dirty mark for formatting-only changes.
    nextTick(() => { programmaticUpdate = false })
  }
}, { immediate: true })
watch(jianpuText, (v) => {
  if (v !== store.currentBatchJianpuText) {
    const isUserEdit = !programmaticUpdate
    store.setBatchJianpuText(v, isUserEdit)
    if (isUserEdit) {
      store.setBatchRenderPageFileIds([])
      setFinalSvgFileIds([])
    }
    errorLine.value = -1
  }
  syncPageStartsFromEditor(v)
})
watch(() => store.svgFileIds, () => {
  if (!isViewingFinal.value) finalSvgFileIds.value = currentPageSvgIds()
})
watch(() => store.currentBatchRenderPageFileIds, (ids) => {
  if (ids.length) setFinalSvgFileIds(ids)
})
watch(() => store.currentPageIndex, () => {
  currentNoteIndex.value = -1
  errorLine.value = -1
  if (!isViewingFinal.value) setFinalSvgFileIds(currentPageSvgIds())
  if (!isViewingFinal.value) flashCurrentPageSection('切换页面')
})

onMounted(() => {
  if (!settings.loaded) void settings.load()
  loadHistory()
  stopHistoryUpdatedListener = listenHistoryUpdated(() => loadHistory(false, { refreshExpanded: false }))
  stopHistoryPagePatchedListener = listenHistoryPagePatched(handleHistoryPagePatched)
})

onUnmounted(() => {
  stopHistoryUpdatedListener?.()
  stopHistoryUpdatedListener = null
  stopHistoryPagePatchedListener?.()
  stopHistoryPagePatchedListener = null
})

function toggleHistory() {
  historyOpen.value = !historyOpen.value
  if (historyOpen.value) loadHistory(false, { refreshExpanded: false })
}

async function loadHistory(
  showLoading = true,
  options: { refreshExpanded?: boolean } = {},
): Promise<void> {
  const seq = ++historyListRequestSeq
  const refreshExpanded = options.refreshExpanded ?? showLoading
  if (showLoading) {
    histLoading.value = true
  }
  try {
    const batches = await requireData(historyApi.list())
    if (seq !== historyListRequestSeq) return
    histBatches.value = batches
    syncExpandedBatchSummary()
    const openId = expandedBatchId.value
    if (openId !== null && refreshExpanded) {
      void refreshExpandedBatch(openId, { clear: false, showLoading: false })
    }
  } catch (e: unknown) {
    if (seq === historyListRequestSeq) {
      log.addError(`加载历史失败：${e instanceof Error ? e.message : String(e)}`)
    }
  } finally {
    if (seq === historyListRequestSeq) {
      histLoading.value = false
    }
  }
}

async function handleDeleteAll(): Promise<void> {
  await requireData(historyApi.deleteAll())
  histBatches.value = []
  expandedBatchId.value = null
  expandedPages.value = []
  loadingBatchId.value = null
  historyDetailEpoch.invalidate()
  message.success('已清空')
}

async function handleDeleteBatch(batchId: number): Promise<void> {
  try {
    await requireData(historyApi.deleteOne(batchId))
    histBatches.value = histBatches.value.filter((batch) => batch.id !== batchId)
    if (expandedBatchId.value === batchId) {
      expandedBatchId.value = null
      expandedPages.value = []
      loadingBatchId.value = null
      historyDetailEpoch.invalidate()
    }
    message.success('已删除')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`删除历史失败：${msg}`)
    message.error(msg)
  }
}

async function toggleBatchExpand(batchId: number): Promise<void> {
  if (expandedBatchId.value === batchId) {
    expandedBatchId.value = null
    expandedPages.value = []
    loadingBatchId.value = null
    historyDetailEpoch.invalidate()
    return
  }
  expandedBatchId.value = batchId
  await refreshExpandedBatch(batchId, { clear: true, showLoading: true })
}

async function refreshExpandedBatch(
  batchId: number,
  options: { clear: boolean; showLoading: boolean },
): Promise<void> {
  const requestToken = historyDetailEpoch.begin()
  if (options.clear) {
    expandedPages.value = []
  }
  if (options.showLoading) {
    loadingBatchId.value = batchId
  }
  try {
    const batch: HistoryBatch = await requireData(historyApi.get(batchId))
    if (historyDetailEpoch.isCurrent(requestToken) && expandedBatchId.value === batchId) {
      expandedPages.value = mergeLockedHistoryPages(batch.pages)
      syncExpandedBatchSummary(batchId)
    }
  } catch (e: unknown) {
    if (historyDetailEpoch.isCurrent(requestToken) && expandedBatchId.value === batchId) {
      log.addError(`加载详情失败：${e instanceof Error ? e.message : String(e)}`)
      expandedPages.value = []
    }
  } finally {
    if (historyDetailEpoch.isCurrent(requestToken) && loadingBatchId.value === batchId) {
      loadingBatchId.value = null
    }
  }
}

async function handleRestorePage(page: HistoryPage): Promise<void> {
  if (store.isBusy) {
    message.warning('识别任务进行中，完成后再恢复历史记录。')
    return
  }

  const batchId = expandedBatchId.value
  if (!batchId) return

  let allPages = expandedPages.value
  let renderPageFileIds: string[] = []
  let batchJianpuText = ''
  let renderPageOcrTexts: HistoryBatch['render_page_ocr_texts'] = []
  let pageIndex = allPages.findIndex((p) => p.id === page.id)
  try {
    const batch = await fetchStableHistoryBatch(batchId)
    if (!batch) return
    renderPageFileIds = batch.render_page_file_ids
    batchJianpuText = batch.jianpu_text || ''
    renderPageOcrTexts = batch.render_page_ocr_texts || []
    if (expandedBatchId.value === batchId) {
      allPages = batch.pages
      expandedPages.value = batch.pages
    }
    pageIndex = allPages.findIndex((p) => p.id === page.id)
  } catch (e: unknown) {
    log.addError(`刷新历史详情失败：${e instanceof Error ? e.message : String(e)}`)
  }
  if (!allPages.length) return

  const migratedPages = allPages.map((p) => {
    const split = splitJianpuAndOcr(p.jianpu_text || '')
    return { page: p, split, jianpu: split.jianpuText }
  })

  store.loadBatch(
    migratedPages.map((r) => ({
      inputFileName: r.page.input_file_name,
      inputFileId: r.page.input_file_id,
      originalFileName: isPreviewableHistoryFile(r.page.input_file_name) ? r.page.input_file_name : '',
      originalFileId: isPreviewableHistoryFile(r.page.input_file_name) ? r.page.input_file_id : '',
      historyPageId: r.page.id,
      historyBatchId: batchId,
      musicxmlFileId: r.page.musicxml_file_id,
      jianpuText: r.jianpu,
      ocrText: r.page.ocr_text || r.split.ocrText,
      svgFileId: r.page.svg_file_id,
      overlayFileId: r.page.overlay_svg_file_id ?? '',
      svgFileIds: r.page.svg_file_id ? [r.page.svg_file_id] : [],
      taskId: r.page.task_id || '',
      startMeasureNumber: r.page.start_measure_number ?? null,
      status: r.page.status as any,
      measureNumberOptions: parseWaitingMeasureOptions(r.page.error_message),
      errorMessage: r.page.error_message,
      ...liveRecognitionTaskPatch(r.page.id, r.page.status),
    })),
    pageIndex >= 0 ? pageIndex : 0,
    renderPageFileIds,
    batchJianpuText,
    renderPageOcrTexts,
  )
  isViewingFinal.value = false
  void validateRestoredBatchFiles(allPages, renderPageFileIds)
  void nextTick(() => flashCurrentPageSection('历史恢复'))

  message.success(`已恢复 ${allPages.length} 页`)
}

async function fetchStableHistoryBatch(batchId: number): Promise<HistoryBatch | null> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const requestToken = historyDetailEpoch.begin()
    const batch = await requireData(historyApi.get(batchId))
    if (expandedBatchId.value !== batchId) return null
    if (historyDetailEpoch.isCurrent(requestToken)) {
      if (loadingBatchId.value === batchId) loadingBatchId.value = null
      return batch
    }
  }
  message.info('历史页面状态正在更新，请稍后重试')
  return null
}

async function validateRestoredBatchFiles(
  pages: HistoryPage[],
  renderPageFileIds: string[] = [],
): Promise<void> {
  const seq = ++restoreCheckSeq
  const fileIds = pages
    .flatMap((entry) => [entry.input_file_id, entry.musicxml_file_id, entry.svg_file_id])
    .concat(renderPageFileIds)
    .filter(Boolean)
  if (!fileIds.length) return

  try {
    const exists = await requireData(filesApi.existsMany(fileIds))
    if (seq !== restoreCheckSeq) return
    const warnings: string[] = []
    for (const entry of pages) {
      const patch: Partial<TaskPage> = {}
      if (entry.input_file_id && !exists[entry.input_file_id]) {
        patch.inputFileId = ''
        patch.originalFileId = ''
        patch.originalFileName = ''
        warnings.push(`${entry.input_file_name}：原始文件已失效`)
      }
      if (entry.musicxml_file_id && !exists[entry.musicxml_file_id]) {
        patch.musicxmlFileId = ''
        warnings.push(`${entry.input_file_name}：MusicXML 已失效`)
      }
      if (entry.svg_file_id && !exists[entry.svg_file_id]) {
        patch.svgFileId = ''
        patch.svgFileIds = []
        warnings.push(`${entry.input_file_name}：SVG 已失效`)
      }
      if (Object.keys(patch).length) {
        store.patchPageByHistoryPageId(entry.id, patch)
      }
    }
    if (warnings.length) {
      log.addLog(`历史恢复部分失效：${warnings.join('，')}`, 'warn')
      message.warning(`${warnings.join('；')}，请重新识别或重新上传。`)
    }
  } catch (e: unknown) {
    if (seq === restoreCheckSeq) {
      log.addLog(`校验历史文件失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
    }
  }
}

function replaceExpandedHistoryPage(page: HistoryPage): void {
  const index = expandedPages.value.findIndex((entry) => entry.id === page.id)
  if (index < 0) return
  expandedPages.value = expandedPages.value.map((entry) => (
    entry.id === page.id ? page : entry
  ))
  syncExpandedBatchSummary()
}

function mergeLockedHistoryPages(pages: HistoryPage[]): HistoryPage[] {
  if (!locallyUpdatingHistoryPageIds.size) return pages
  return pages.map((page) => {
    if (!locallyUpdatingHistoryPageIds.has(page.id)) return page
    return expandedPages.value.find((localPage) => localPage.id === page.id) ?? page
  })
}

function handleHistoryPagePatched(detail: HistoryPagePatchDetail): void {
  historyDetailEpoch.invalidate()
  if (loadingBatchId.value === expandedBatchId.value) {
    loadingBatchId.value = null
  }
  applyExpandedHistoryPagePatch(detail.id, detail.patch)
}

function applyExpandedHistoryPagePatch(
  pageId: number,
  patch: HistoryPagePatchDetail['patch'],
): boolean {
  const page = expandedPages.value.find((entry) => entry.id === pageId)
  if (!page) return false
  replaceExpandedHistoryPage({ ...page, ...patch })
  return true
}

function syncExpandedBatchSummary(batchId = expandedBatchId.value): void {
  if (batchId === null || !expandedPages.value.length) return
  const status = batchStatus(expandedPages.value.map((page) => page.status))
  const firstFileName = expandedPages.value[0]?.input_file_name ?? ''
  histBatches.value = histBatches.value.map((batch) => (
    batch.id === batchId
      ? {
          ...batch,
          status,
          page_count: expandedPages.value.length,
          first_file_name: firstFileName || batch.first_file_name,
        }
      : batch
  ))
}

function batchStatus(statuses: string[]): string {
  if (statuses.some((status) => status === 'failed')) return 'failed'
  if (statuses.some((status) => status === 'waiting')) return 'waiting'
  if (statuses.some((status) => status === 'processing' || status === 'pending')) return 'processing'
  return 'completed'
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function historyStatusClass(status: string): string {
  if (status === 'completed') return 'ok'
  if (status === 'processing' || status === 'pending' || status === 'waiting') return 'processing'
  if (status === 'unrecognized') return 'unrecognized'
  return 'err'
}

function isWaitingStatus(status: string): boolean {
  return status === 'waiting'
}

async function handleHistoryPageClick(page: HistoryPage): Promise<void> {
  if (checkingHistoryPageIds.has(page.id) || selectingHistoryPageIds.has(page.id)) return
  if (!isWaitingStatus(page.status)) {
    await handleRestorePage(page)
    return
  }

  checkingHistoryPageIds.add(page.id)
  historyDetailEpoch.invalidate()
  try {
    const latest = await requireData(historyApi.getPage(page.id))
    replaceExpandedHistoryPage(latest)
    syncStoreFromHistoryPage(latest)
    const action = historyPageOpenAction(latest.status)
    if (action === 'choose') {
      const options = parseWaitingMeasureOptions(latest.error_message)
      if (!options.length) {
        message.warning('没有可选的小节号候选')
        return
      }
      histPickerPage.value = latest
      histPickerOptions.value = options
      histPickerShow.value = true
      return
    }
    if (action === 'wait') {
      message.info('页面状态已更新，正在处理中')
      return
    }
    await handleRestorePage(latest)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    message.error(`无法确认页面最新状态：${msg}`)
    log.addError(`确认历史页面状态失败：${msg}`)
  } finally {
    checkingHistoryPageIds.delete(page.id)
  }
}

async function onHistPickerConfirm(selected: number): Promise<void> {
  const page = histPickerPage.value
  histPickerShow.value = false
  histPickerPage.value = null
  if (!page) return
  await applyHistoryMeasureSelection(page, selected)
}

async function applyHistoryMeasureSelection(page: HistoryPage, selected: number): Promise<void> {
  if (selectingHistoryPageIds.has(page.id)) return
  selectingHistoryPageIds.add(page.id)
  locallyUpdatingHistoryPageIds.add(page.id)
  historyDetailEpoch.invalidate()
  const processingPage: HistoryPage = {
    ...page,
    start_measure_number: selected,
    status: 'processing',
    error_message: '正在重新渲染',
  }
  replaceExpandedHistoryPage(processingPage)
  syncStoreFromHistoryPage(processingPage)
  notifyHistoryPagePatched(historyPagePatchFromPage(processingPage))

  const options = parseWaitingMeasureOptions(page.error_message)
  try {
    let svgFileId = page.svg_file_id
    let svgFileIds = page.svg_file_id ? [page.svg_file_id] : []
    let jianpuText = page.jianpu_text
    if (page.musicxml_file_id && selected !== options[0]) {
      const rendered = await requireData(renderApi.jianpuSvg({
        musicxml_file_id: page.musicxml_file_id,
        page_image_file_id: page.input_file_id || undefined,
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        measure_number_mode: settings.measureNumberMode,
        start_measure_number: selected,
      }))
      svgFileId = rendered.svg_file_id
      svgFileIds = renderResponsePageIds(rendered.pages, rendered.svg_file_id)
    } else if (!page.musicxml_file_id && page.jianpu_text.trim()) {
      const rendered = await requireData(renderApi.jianpuTextSvg({
        jianpu_text: page.jianpu_text,
        page_image_file_id: page.input_file_id || undefined,
        include_ocr_text: false,
        measure_number_mode: settings.measureNumberMode,
        title: page.input_file_name || 'AI 简谱',
        start_measure_number: selected,
      }))
      svgFileId = rendered.svg_file_id
      svgFileIds = renderResponsePageIds(rendered.pages, rendered.svg_file_id)
      jianpuText = rendered.jianpu_text || page.jianpu_text
    }
    const updated = await requireData(historyApi.updatePage(page.id, {
      task_id: '',
      start_measure_number: selected,
      jianpu_text: jianpuText,
      svg_file_id: svgFileId,
      status: 'completed',
      error_message: '',
    }))
    replaceExpandedHistoryPage(updated)
    syncStoreFromHistoryPage(updated)
    store.patchPageByHistoryPageId(updated.id, { svgFileIds })
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    notifyHistoryPagePatched(historyPagePatchFromPage(updated))
    message.success('已应用起始小节号')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    const failedMessage = failedMeasureSelectionMessage(options, msg)
    const failedPage: HistoryPage = {
      ...page,
      start_measure_number: selected,
      status: 'waiting',
      error_message: failedMessage,
    }
    try {
      const updated = await requireData(historyApi.updatePage(page.id, {
        task_id: '',
        start_measure_number: selected,
        status: 'waiting',
        error_message: failedMessage,
      }))
      replaceExpandedHistoryPage(updated)
      syncStoreFromHistoryPage(updated)
      notifyHistoryPagePatched(historyPagePatchFromPage(updated))
    } catch (persistError: unknown) {
      replaceExpandedHistoryPage(failedPage)
      syncStoreFromHistoryPage(failedPage)
      notifyHistoryPagePatched(historyPagePatchFromPage(failedPage))
      log.addLog(`保存小节号失败状态失败：${persistError instanceof Error ? persistError.message : String(persistError)}`, 'warn')
    }
    message.error(msg)
    log.addError(`选择小节号失败：${msg}`)
  } finally {
    locallyUpdatingHistoryPageIds.delete(page.id)
    selectingHistoryPageIds.delete(page.id)
  }
}

function syncStoreFromHistoryPage(page: HistoryPage): void {
  const split = splitJianpuAndOcr(page.jianpu_text || '')
  store.patchPageByHistoryPageId(page.id, {
    historyPageId: page.id,
    inputFileName: page.input_file_name,
    inputFileId: page.input_file_id,
    originalFileName: isPreviewableHistoryFile(page.input_file_name) ? page.input_file_name : '',
    originalFileId: isPreviewableHistoryFile(page.input_file_name) ? page.input_file_id : '',
    musicxmlFileId: page.musicxml_file_id,
    jianpuText: split.jianpuText,
    ocrText: page.ocr_text || split.ocrText,
    svgFileId: page.svg_file_id,
    overlayFileId: page.overlay_svg_file_id ?? '',
    svgFileIds: page.svg_file_id ? [page.svg_file_id] : [],
    taskId: page.task_id || '',
    historyBatchId: page.batch_id ?? null,
    startMeasureNumber: page.start_measure_number ?? null,
    status: page.status as any,
    progressPercent: page.status === 'processing' ? 99 : 100,
    progressMessage: page.status === 'waiting'
      ? '等待选择起始小节号'
      : page.status === 'completed'
        ? '识别完成'
        : page.status === 'processing'
          ? (page.error_message || '正在重新渲染')
          : page.error_message,
    measureNumberOptions: page.status === 'waiting' ? parseWaitingMeasureOptions(page.error_message) : [],
    errorMessage: page.error_message,
    ...liveRecognitionTaskPatch(page.id, page.status),
  })
}

function resolveMissingFileId(msg: string): string | null {
  const match = msg.match(/文件不存在[:：]\s*([A-Za-z0-9_-]+)/)
  return match?.[1] ?? null
}

function handleMissingMusicxml(errorMessage: string): string {
  const missingId = resolveMissingFileId(errorMessage)
  if (!missingId || missingId !== store.musicxmlFileId) return errorMessage
  store.setMusicxml('', '')
  setFinalSvgFileIds([])
  return '当前 MusicXML 引用已失效，请回到"识别"页重新识别。'
}

function extractErrorLineFromMessage(msg: string): number {
  const lineMatch = msg.match(/第\s*(\d+)\s*行/)
  if (!lineMatch) return -1
  const sectionLine = Number(lineMatch[1])

  const sections = parseJianpuPageSections(jianpuText.value)
  if (sections.length === 1 && sections[0].markerLineIndex < 0) {
    return sectionLine - 1
  }

  const pageMatch = msg.match(/第\s*(\d+)\s*页/)
  if (pageMatch) {
    const pageNumber = Number(pageMatch[1])
    const section = sections.find((s) => s.pageIndex === pageNumber - 1)
      ?? sections[pageNumber - 1]
    if (section) {
      const L = section.markerLineIndex
      if (L < 0) return sectionLine - 1
      if (section.pageIndex === 0 && L > 0) {
        return sectionLine <= L ? sectionLine - 1 : sectionLine
      }
      return L + sectionLine
    }
  }

  for (let i = 0; i < sections.length; i++) {
    const section = sections[i]
    if (!section.body.trim()) continue
    const bodyLineCount = section.body.split('\n').length
    if (sectionLine <= bodyLineCount) {
      const L = section.markerLineIndex
      if (L < 0) return sectionLine - 1
      if (i === 0 && L > 0) {
        return sectionLine <= L ? sectionLine - 1 : sectionLine
      }
      return L + sectionLine
    }
  }

  return sectionLine - 1
}

async function exportScore(): Promise<void> {
  store.setBusy(true)
  errorLine.value = -1
  try {
    const format = exportFormat.value
    if (format === 'mid') {
      const page = currentExportPage()
      const result = page.jianpuText.trim()
        ? await requireData(exportApi.exportMidiText({ jianpu_text: page.jianpuText, filename: 'score.mid', title: '简谱' }))
        : await requireData(exportApi.exportMidi(store.musicxmlFileId, 'score.mid'))
      downloadFile(result.file_id, result.filename)
      log.addLog(`导出完成：${result.filename}`)
      message.success('导出完成')
      return
    }
    if (format === 'musicxml') {
      const page = currentExportPage()
      const result = page.jianpuText.trim()
        ? await requireData(exportApi.exportMusicXmlText({ jianpu_text: page.jianpuText, filename: 'score.musicxml', title: '简谱' }))
        : await requireData(exportApi.exportMusicXml({
            musicxml_file_id: store.musicxmlFileId,
            filename: 'score.musicxml',
            title: '简谱',
            target_key: settings.targetKey,
            start_measure_number: batchStartMeasureNumber.value ?? settings.startMeasureNumber ?? undefined,
          }))
      downloadFile(result.file_id, result.filename)
      log.addLog(`导出完成：${result.filename}`)
      message.success('导出完成')
      return
    }
    if (format === 'png') {
      const ids = await renderExportSvgIds()
      const svgFileId = ids[Math.min(finalRenderPageIndex.value, ids.length - 1)]
      if (!svgFileId) throw new Error('暂无可导出的 A4 页面')
      const png = await svgToPngBlob(exportApi.getDownloadURL(svgFileId))
      downloadBlob(png, 'jianpu.png')
      log.addLog('导出完成：jianpu.png')
      message.success('导出完成')
      return
    }

    const svgIds = await renderExportSvgIds()
    if (!svgIds.length) throw new Error('暂无可导出的页面')
    const imagePages: Blob[] = []
    const skippedPages: number[] = []
    for (let index = 0; index < svgIds.length; index++) {
      try {
        imagePages.push(await svgToJpegBlob(exportApi.getDownloadURL(svgIds[index])))
      } catch {
        skippedPages.push(index + 1)
      }
    }
    if (!imagePages.length) throw new Error('所有页面导出失败，无可用内容')
    const result = await requireData(exportApi.exportPdf(imagePages, 'jianpu.pdf'))
    downloadFile(result.file_id, result.filename)
    if (skippedPages.length) {
      log.addLog(`导出完成（跳过 ${skippedPages.length} 页失败页）：${result.filename}`)
      message.warning(`已跳过 ${skippedPages.length} 张 A4 页：${skippedPages.join('、')}`)
    } else {
      log.addLog(`导出完成：${result.filename}`)
    }
    message.success('导出完成')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    errorLine.value = extractErrorLineFromMessage(raw)
    log.addError(`导出失败：${raw}`)
    message.error(raw)
  } finally {
    store.setBusy(false)
  }
}

function downloadFile(fileId: string, filename: string): void {
  const url = exportApi.getDownloadURL(fileId)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

function currentExportPage(): TaskPage {
  const page = store.currentPage
  return {
    ...(page ?? {
      id: 'current',
      historyPageId: store.historyPageId,
      historyBatchId: null,
      inputFileName: store.inputFileName,
      inputFileId: store.inputFileId,
      originalFileName: store.originalFileName,
      originalFileId: store.originalFileId,
      musicxmlFileId: store.musicxmlFileId,
      musicxmlText: store.currentPage?.musicxmlText ?? '',
      jianpuText: store.currentBatchJianpuText || store.jianpuText,
      ocrText: store.ocrText,
      jianpuDirty: store.jianpuDirty,
      svgFileId: store.svgFileId,
      svgFileIds: store.svgFileIds,
      startMeasureNumber: store.startMeasureNumber,
      status: 'completed',
      errorMessage: '',
    }),
    jianpuText: jianpuText.value,
    ocrText: store.ocrText,
    svgFileId: finalSvgFileId.value || store.svgFileId,
    svgFileIds: finalSvgFileIds.value.length ? finalSvgFileIds.value : store.svgFileIds,
  } as TaskPage
}

function batchRenderSourcePages(): TaskPage[] {
  if (!store.currentBatchPages.length) return [currentExportPage()]
  return store.currentBatchPages.map((page) =>
    page.id === store.currentPage?.id ? currentExportPage() : page,
  )
}

function syncPageStartsFromEditor(text: string): void {
  if (!hasJianpuPageMarkers(text)) return
  const sections = parseJianpuPageSections(text)
  const batchPages = store.currentBatchPages
  if (sections.length !== batchPages.length) return
  sections.forEach((section, order) => {
    const page = batchPages[section.pageIndex] ?? batchPages[order]
    if (page && page.startMeasureNumber !== section.startMeasureNumber) {
      store.patchPageById(page.id, { startMeasureNumber: section.startMeasureNumber })
    }
  })
}

/** 让编辑器跳转到指定行并闪两下；同一行可重复触发。 */
function requestEditorFlash(line: number): void {
  if (line < 0) return
  flashLine.value = -1
  void nextTick(() => { flashLine.value = line })
}

/**
 * 计算当前页（左侧图片）对应的编辑器文本段落行号，并触发闪烁。
 * 同时校验左侧图片与右侧 P1/P2 段落是否一一对应；不一致时记录告警。
 * @param source 触发来源，用于告警日志
 */
function flashCurrentPageSection(source: string): void {
  const text = store.currentBatchJianpuText
  if (!hasJianpuPageMarkers(text)) return
  const sections = parseJianpuPageSections(text)
  const batchPages = store.currentBatchPages
  const currentPage = store.currentPage
  const localIdx = currentPage ? batchPages.indexOf(currentPage) : -1

  if (sections.length !== batchPages.length) {
    log.addLog(
      `[${source}] 左侧图片（${batchPages.length} 页）与右侧编辑区段落（${sections.length} 段）数量不一致，可能不同步`,
      'warn',
    )
  }
  if (localIdx < 0) return
  const section = sections[localIdx] ?? sections[0]
  if (section && section.markerLineIndex >= 0) {
    requestEditorFlash(section.markerLineIndex)
  }
}

function mergePendingRecognitionResults(): void {
  const pendingIds = new Set(store.currentBatchJianpuPendingPageIds)
  if (!pendingIds.size) return
  let merged = jianpuText.value
  store.currentBatchPages.forEach((page, pageIndex) => {
    if (!pendingIds.has(page.id)) return
    merged = replaceJianpuSectionBody(merged, pageIndex, page.jianpuText, page)
  })
  store.setBatchJianpuText(merged, true)
  store.clearBatchJianpuPendingPages()
  store.setBatchRenderPageFileIds([])
  setFinalSvgFileIds([])
  message.success(`已合入 ${pendingIds.size} 页识别结果`)
}

async function renderExportSvgIds(): Promise<string[]> {
  if (store.currentBatchRenderPageOcrDirty) return renderFinalBatch()
  if (store.currentBatchRenderPageFileIds.length) {
    setFinalSvgFileIds(store.currentBatchRenderPageFileIds)
    return finalSvgFileIds.value
  }
  return renderFinalBatch()
}

async function renderFinalBatch(): Promise<string[]> {
  const pages = buildBatchRenderPages()
  if (!pages.length) throw new Error('暂无可渲染的简谱内容')
  const result = await requireData(renderApi.batchA4({
    pages,
    source_pages: buildBatchRenderSourcePages(),
    render_page_ocr_texts: currentRenderPageOcrTextsForRequest(),
    target_key: settings.targetKey,
    accidental_mode: settings.accidentalMode,
    measure_number_mode: settings.measureNumberMode,
    title: '简谱',
  }))
  const ids = renderResponsePageIds(result.pages, result.svg_file_id)
  setFinalSvgFileIds(ids)
  store.setBatchRenderPageFileIds(ids)
  store.setBatchRenderPageOcrTexts(
    renderResponsePageOcrTexts(result.pages),
    false,
  )
  await persistBatchRenderPages(ids)
  await persistBatchRenderPageOcrTexts()
  store.markBatchRenderPageOcrClean()
  return ids
}

function buildBatchRenderPages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: jianpuText.value,
    title: '简谱',
  })
}

function buildBatchRenderSourcePages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: jianpuText.value,
    title: '简谱',
  })
}

function currentRenderPageOcrTextsForRequest() {
  return renderPageOcrTextsForRequest(
    store.currentBatchRenderPageOcrTextEntries(),
    store.currentBatchRenderPageOcrDirty,
  )
}

function currentPageSvgIds(): string[] {
  return store.svgFileIds.length ? store.svgFileIds : (store.svgFileId ? [store.svgFileId] : [])
}

function setFinalSvgFileIds(ids: string[]): void {
  finalSvgFileIds.value = [...ids]
  finalRenderPageIndex.value = Math.max(
    0,
    Math.min(finalRenderPageIndex.value, finalSvgFileIds.value.length - 1),
  )
}

function currentHistoryBatchId(): number | null {
  return store.currentBatchPages.find((page) => page.historyBatchId)?.historyBatchId ?? null
}

async function persistBatchRenderPages(
  ids: string[],
  batchId: number | null = currentHistoryBatchId(),
): Promise<void> {
  if (!batchId || !ids.length) return
  try {
    const updated = await requireData(historyApi.updateBatchRenderPages(batchId, {
      render_page_file_ids: ids,
    }))
    store.setBatchRenderPageFileIds(updated.render_page_file_ids)
  } catch (e: unknown) {
    log.addLog(`保存连续 A4 渲染页失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
  }
}

async function persistBatchRenderPageOcrTexts(
  batchId: number | null = currentHistoryBatchId(),
): Promise<void> {
  if (!batchId) return
  try {
    const updated = await requireData(historyApi.updateBatchRenderPageOcrTexts(batchId, {
      pages: store.currentBatchRenderPageOcrTextEntries(),
    }))
    store.setBatchRenderPageOcrTexts(updated.render_page_ocr_texts || [], false)
  } catch (e: unknown) {
    log.addLog(`保存连续 A4 文字层失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
  }
}

async function musicxmlToJianpu(): Promise<void> {
  store.setBusy(true)
  try {
    const result = await requireData(convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      page_image_file_id: store.originalFileId || undefined,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
      start_measure_number: batchStartMeasureNumber.value ?? settings.startMeasureNumber ?? undefined,
    }))
    const split = splitJianpuAndOcr(result.jianpu_text)
    store.setJianpu(split.jianpuText)
    store.setBatchJianpuText(composeJianpuPageText(store.currentBatchPages), false)
    store.setOcrText(split.ocrText || store.ocrText)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    log.addLog('已转换为简谱')
    message.success('转换完成')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`转换失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function saveJianpu(): Promise<void> {
  if (!canSaveCurrentPage.value) {
    message.warning('暂无可保存内容')
    return
  }
  store.setBusy(true)
  errorLine.value = -1
  try {
    const ids = store.currentBatchRenderPageOcrDirty
      ? await renderFinalBatch()
      : (finalSvgFileIds.value.length ? finalSvgFileIds.value : currentPageSvgIds())
    await persistRenderedHistory(ids[0] || store.svgFileId || '', ids)
    store.markBatchJianpuClean()
    store.markBatchRenderPageOcrClean()
    log.addLog('已保存 OMR、简谱和 OCR 信息')
    message.success('已保存')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    errorLine.value = extractErrorLineFromMessage(raw)
    log.addError(`保存失败：${raw}`)
    message.error(raw)
  } finally {
    store.setBusy(false)
  }
}

function handleOcrTextUpdate(value: string): void {
  store.setBatchRenderPageOcrText(finalRenderPageIndex.value, value, true)
}

function applyReturnedOcr(value?: string | null): void {
  if (!value || store.ocrText.trim()) return
  store.setOcrText(value)
}


async function renderSvg(): Promise<void> {
  store.setBusy(true)
  errorLine.value = -1
  try {
    await renderFinalBatch()
    isViewingFinal.value = true
    log.addLog('已渲染 SVG')
    message.success('渲染完成')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    errorLine.value = extractErrorLineFromMessage(msg)
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

function handleStartMeasureChange(value: number | null): void {
  const first = firstBatchPage()
  if (first?.id) {
    store.patchPageById(first.id, { startMeasureNumber: value })
  } else {
    store.setPageStartMeasureNumber(value)
  }
  const baseText = jianpuText.value || composeJianpuPageText(store.currentBatchPages)
  jianpuText.value = updateJianpuPageStart(baseText, 0, value, first?.inputFileName ?? '')
  store.setBatchRenderPageFileIds([])
  setFinalSvgFileIds([])
}

async function toggleFinalView(): Promise<void> {
  if (isViewingFinal.value) { isViewingFinal.value = false; return }
  isRenderingFinal.value = true
  store.setBusy(true)
  errorLine.value = -1
  try {
    await renderFinalBatch()
    isViewingFinal.value = true
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    errorLine.value = extractErrorLineFromMessage(msg)
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
    isRenderingFinal.value = false
  }
}

async function persistRenderedHistory(svgFileId: string, renderPageFileIds: string[]): Promise<void> {
  const savedJianpu = jianpuText.value
  if (savedJianpu.trim()) {
    await requireData(renderApi.normalizeJianpuText({ jianpu_text: savedJianpu, title: '简谱' }))
  }
  const sections = parseJianpuPageSections(savedJianpu)
  const currentPageIndex = Math.max(0, currentBatchLocalIndex.value)
  const currentSection = sections.find((section) => section.pageIndex === currentPageIndex)
    ?? sections[currentPageIndex]
  const historyBatchId = currentHistoryBatchId()
  if (historyBatchId) {
    await persistBatchJianpuText(historyBatchId, savedJianpu)
  }
  const sourcePageText = currentSection?.body
    ?? store.currentPage?.jianpuText
    ?? store.jianpuText
  const sourceSvgFileId = store.currentPage?.svgFileId || store.svgFileId || svgFileId
  const payload = {
    musicxml_file_id: store.musicxmlFileId,
    jianpu_text: sourcePageText,
    ocr_text: store.ocrText,
    svg_file_id: sourceSvgFileId,
    start_measure_number: currentSection
      ? currentSection.startMeasureNumber
      : (store.startMeasureNumber ?? null),
    status: 'completed',
    error_message: '',
  }

  if (store.historyPageId) {
    const updated = await requireData(historyApi.updatePage(store.historyPageId, payload))
    replaceExpandedHistoryPage(updated)
    await persistOtherHistoryPageSections(savedJianpu, store.historyPageId)
    await persistBatchRenderPages(renderPageFileIds)
    await persistBatchRenderPageOcrTexts()
    return
  }

  const batchPages = store.currentBatchPages.length
    ? store.currentBatchPages
    : [currentExportPage()]
  const created = await requireData(historyApi.create({
    jianpu_text: savedJianpu,
    render_page_file_ids: renderPageFileIds,
    render_page_ocr_texts: store.currentBatchRenderPageOcrTextEntries(),
    pages: batchPages.map((page, pageIndex) => {
      const section = sections.find((item) => item.pageIndex === pageIndex) ?? sections[pageIndex]
      return {
        input_file_name: page.inputFileName,
        input_file_id: page.inputFileId,
        musicxml_file_id: page.musicxmlFileId,
        jianpu_text: section?.body ?? page.jianpuText,
        ocr_text: page.ocrText,
        svg_file_id: page.svgFileId || (pageIndex === currentPageIndex ? sourceSvgFileId : ''),
        start_measure_number: section
          ? section.startMeasureNumber
          : (page.startMeasureNumber ?? null),
        status: 'completed',
        error_message: '',
      }
    }),
  }))
  created.pages.forEach((createdPage, pageIndex) => {
    const page = batchPages[pageIndex]
    if (!page) return
    store.patchPageById(page.id, {
      historyPageId: createdPage.id,
      historyBatchId: created.id,
      jianpuText: createdPage.jianpu_text,
      startMeasureNumber: createdPage.start_measure_number,
    })
  })
  const pageId = created.pages[currentPageIndex]?.id ?? created.pages[0]?.id
  if (pageId) {
    await persistBatchRenderPages(renderPageFileIds, created.id)
    await persistBatchRenderPageOcrTexts(created.id)
    await loadHistory()
  }
}

async function persistOtherHistoryPageSections(
  text: string,
  currentHistoryPageId: number,
): Promise<void> {
  const sections = parseJianpuPageSections(text)
  for (let pageIndex = 0; pageIndex < store.currentBatchPages.length; pageIndex += 1) {
    const page = store.currentBatchPages[pageIndex]
    const section = sections.find((item) => item.pageIndex === pageIndex) ?? sections[pageIndex]
    if (!page || !section) continue
    store.patchPageById(page.id, {
      jianpuText: section.body,
      startMeasureNumber: section.startMeasureNumber,
    })
    if (!page.historyPageId || page.historyPageId === currentHistoryPageId) continue
    const updated = await requireData(historyApi.updatePage(page.historyPageId, {
      jianpu_text: section.body,
      start_measure_number: section.startMeasureNumber,
    }))
    replaceExpandedHistoryPage(updated)
  }
}

function firstBatchPage(): TaskPage | null {
  return store.currentBatchPages[0] ?? store.currentPage
}

async function persistBatchJianpuText(batchId: number, text: string): Promise<void> {
  try {
    await requireData(historyApi.updateBatchJianpuText(batchId, { jianpu_text: text }))
  } catch (e: unknown) {
    log.addLog(`保存批次简谱文本失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
  }
}

</script>

<style scoped>
.workspace {
  height: 100%;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.ws-history {
  width: 0;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-elevated);
  overflow: hidden;
  transition: width 0.2s ease;
}

.ws-history.open {
  width: 240px;
}

.ws-hist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.ws-hist-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.ws-hist-actions {
  display: flex;
  gap: 2px;
}

.ws-hist-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.hist-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

.hist-batch {
  border-radius: var(--radius-sm);
  margin-bottom: 2px;
}

.hist-batch-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease;
}

.hist-batch-head:hover {
  background: var(--accent-light);
}

.hist-delete {
  width: 20px;
  height: 20px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.hist-delete:hover {
  background: rgba(220, 38, 38, 0.08);
  color: var(--danger);
}

.hist-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.hist-dot.small {
  width: 4px;
  height: 4px;
}

.hist-dot.ok { background: var(--success); }
.hist-dot.err { background: var(--danger); }
.hist-dot.unrecognized { background: var(--text-tertiary); }
.hist-dot.processing {
  background: var(--warning);
  animation: pulse-blink 1.5s ease-in-out infinite;
}

@keyframes pulse-blink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.2); }
}

.hist-batch-name {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hist-batch-count {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-surface);
  padding: 1px 5px;
  border-radius: 8px;
  flex-shrink: 0;
}

.hist-waiting-label {
  font-size: 10px;
  color: #1f2937;
  background: var(--warning);
  padding: 1px 5px;
  border-radius: 999px;
  flex-shrink: 0;
  font-weight: 600;
}

.hist-expand-icon {
  color: var(--text-tertiary);
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.hist-expand-icon.rotated {
  transform: rotate(90deg);
}

.hist-batch-meta {
  font-size: 10px;
  color: var(--text-tertiary);
  padding: 0 8px 4px 20px;
}

.hist-pages {
  padding: 2px 0 4px 20px;
}

.hist-loading {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 4px 0;
}

.hist-page-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease;
}

.hist-page-item:hover {
  background: var(--accent-light);
}

.hist-unrecognized-label {
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--bg-surface);
  padding: 1px 5px;
  border-radius: 999px;
  flex-shrink: 0;
}

.hist-page-waiting {
  background: var(--accent-light);
}

.hist-page-waiting:hover {
  background: var(--accent-light-hover, var(--accent-light));
}

.hist-page-name {
  font-size: 11px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.ws-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 10px;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.ws-toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.ws-toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.hist-toggle {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.hist-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.toolbar-sep {
  width: 1px;
  height: 20px;
  background: var(--border);
  margin: 0 4px;
}

.page-nav {
  display: flex;
  align-items: center;
  gap: 2px;
}

.page-indicator {
  font-size: 12px;
  color: var(--text-tertiary);
  min-width: 36px;
  text-align: center;
}

.ws-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.ws-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  overflow: hidden;
}

.ws-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.panel-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.render-page-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  color: var(--text-tertiary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.panel-head-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-right: 6px;
  padding-right: 6px;
  border-right: 1px solid var(--border-soft);
}

.meta-label {
  font-weight: 400;
  color: var(--text-tertiary);
  font-size: 10px;
  text-transform: none;
  letter-spacing: 0;
  white-space: nowrap;
}

.panel-filename {
  font-weight: 400;
  color: var(--text-tertiary);
  font-size: 10px;
  text-transform: none;
}

.ws-panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
  padding: 6px;
}

.empty-hint {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .ws-layout {
    grid-template-columns: 1fr;
  }

  .ws-history.open {
    width: 200px;
  }
}
</style>
