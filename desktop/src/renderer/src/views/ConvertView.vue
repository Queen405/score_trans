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
              :class="['hist-page-item', {
                'hist-page-dragging': draggedPageIndex === pi,
                'hist-page-drag-over': dragOverIndex === pi && draggedPageIndex !== null && draggedPageIndex !== pi,
              }]"
              :draggable="canReorderBatch"
              @click="handleHistoryPageClick(page)"
              @dragstart="canReorderBatch ? handlePageDragStart($event, pi) : undefined"
              @dragover.prevent="canReorderBatch ? handlePageDragOver(pi) : undefined"
              @drop.prevent="canReorderBatch ? handlePageDrop(pi) : undefined"
              @dragend="handlePageDragEnd"
            >
              <span :class="['hist-dot small', historyStatusClass(page.status)]" />
              <span class="hist-page-name">{{ page.input_file_name || `第${pi + 1}页` }}</span>
              <span
                v-if="page.status === 'unrecognized'"
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
            @click="resetAll"
          >
            重置
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
            <div
              v-if="canEditMarkers"
              class="marker-edit-controls"
            >
              <n-button
                size="tiny"
                :type="editMode ? 'primary' : 'default'"
                @click="toggleEditMode"
              >
                编辑标记
              </n-button>
              <template v-if="editMode">
                <span class="deleted-count">已删除 {{ deletedEntityIds.size }}</span>
                <n-button
                  size="tiny"
                  type="warning"
                  :loading="applying"
                  @click="applyCorrections"
                >
                  应用修正
                </n-button>
              </template>
            </div>
          </div>
          <div class="ws-panel-body">
            <original-preview
              :file-id="store.originalFileId"
              :file-name="store.originalFileName"
              :overlay-file-id="store.overlayFileId"
              :source-map-file-id="store.sourceMapFileId"
              :clickable-source-ids="clickableSourceIds"
              :selected-source-id="selectedSourceId"
              :editable="editMode"
              :entities="correctableEntities"
              :deleted-entity-ids="deletedEntityIds"
              :entity-width="correctableSheet?.width"
              :entity-height="correctableSheet?.height"
              @select-source="handleOriginalSourceClick"
              @toggle-delete="toggleEntityDelete"
            />
          </div>
        </div>

        <div class="ws-panel ws-right">
          <div class="ws-panel-head">
            <span>{{ isViewingFinal ? '最终渲染' : '简谱编辑' }}</span>
            <div class="panel-head-actions">
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal"
                @click="transposeOctaveShift(1)"
              >
                升八度
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal"
                @click="transposeOctaveShift(-1)"
              >
                降八度
              </n-button>
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
            <publication-preview
              v-if="isViewingFinal && finalSvgFileId"
              ref="svgPreviewRef"
              :svg-file-id="finalSvgFileId"
              :ocr-text="finalRenderPageOcrText"
              :current-note-index="currentNoteIndex"
              editable-ocr
              @update:ocr-text="handleOcrTextUpdate"
              @update:text-attachment="handleTextAttachmentUpdate"
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
              ref="jianpuEditorRef"
              v-model="jianpuText"
              :current-note-index="currentNoteIndex"
              :initial-measure-number="initialMeasureNumber"
              :syntax-highlight="settings.jianpuSyntaxHighlight"
              :error-line="errorLine"
              :flash-line="flashLine"
              @update:initial-measure-number="initialMeasureNumber = $event"
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
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import { convertApi } from '../api/convert'
import { correctApi } from '../api/correct'
import { usePublicationRender } from '../composables/usePublicationRender'
import { downloadBlob, exportApi } from '../api/export'
import { historyApi } from '../api/history'
import { ApiError, fetchFileBlob, requireData } from '../api/client'
import { filesApi } from '../api/files'
import type {
  CorrectableEntityDTO,
  HistoryBatchListItem,
  HistoryBatch,
  HistoryPage,
  RenderedSvgPage,
  SheetEntitiesDTO,
} from '../models/types'
import type { TaskPage, TaskPageStatus } from '../stores/workspace'
import JianpuEditor from '../components/JianpuEditor.vue'
import JianpuPlayer from '../components/JianpuPlayer.vue'
import OriginalPreview from '../components/OriginalPreview.vue'
import PublicationPreview from '../components/PublicationPreview.vue'
import { splitJianpuAndOcr } from '../utils/ocrText'
import {
  hasJianpuPageMarkers,
  parseJianpuPageSections,
  replaceJianpuSectionBody,
  restoreJianpuPageText,
  serializeJianpuPageSections,
} from '../utils/jianpuPageSections'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import { createRequestEpoch } from '../utils/asyncCoordination'
import { trackTextAnchors } from '../utils/textAnchorTracking'
import { sourceAnchorRange } from '../utils/sourceAnchorSelection'
import { findNotePageIndex } from '../utils/jianpuPlayback'
import { transposeOctave } from '../utils/jianpuTranspose'
import {
  buildBatchRenderRequests,
  renderPageOcrTextsForRequest,
  renderResponsePageIds,
  renderResponsePageOcrTexts,
} from '../utils/batchRender'
import { isPreviewableHistoryFile } from '../utils/historyPageState'
import {
  listenHistoryPagePatched,
  listenHistoryUpdated,
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
import { NButton, NSelect, NIcon, NPopconfirm, useMessage } from 'naive-ui'

const store = useWorkspaceStore()
const settings = useSettingsStore()
const publicationRender = usePublicationRender()
const log = useLogStore()
const message = useMessage()
const jianpuEditorRef = ref<{ selectRange: (start: number, end: number) => boolean } | null>(null)
const svgPreviewRef = ref<{
  highlightSource: (sourceId: string) => Promise<boolean>
} | null>(null)
const selectedSourceId = ref('')
const editMode = ref(false)
const deletedEntityIds = ref<Set<string>>(new Set())
const correctableSheet = ref<SheetEntitiesDTO | null>(null)
const correctableEntities = computed<CorrectableEntityDTO[]>(
  () => correctableSheet.value?.entities ?? [],
)
const applying = ref(false)
let entityLoadController: AbortController | null = null

const canEditMarkers = computed(() => (
  !!store.omrFileId
  && !!store.sourceMapFileId
  && !!store.originalMusicxml
  && /\.(png|jpe?g|tiff?|webp)$/i.test(store.originalFileName)
))

const renderSourcePageLookup = ref<Record<string, number>>({})
interface NoteIndexRange {
  start: number | null
  end: number | null
}
const renderPageNoteIndexRanges = ref<NoteIndexRange[]>([])
const clickableSourceIds = computed(() => {
  if (isViewingFinal.value && !finalSvgFileId.value) return []
  return [...new Set(store.textAnchors.map((anchor) => anchor.source_id))]
})

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
const initialMeasureNumber = ref(1)
const initialMeasureNumberStorageKey = 'score-trans.initial-measure-number'
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
const expandedBatchJianpuText = ref('')
const loadingBatchId = ref<number | null>(null)
const draggedPageIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
const isReordering = ref(false)
let stopHistoryUpdatedListener: (() => void) | null = null
let stopHistoryPagePatchedListener: (() => void) | null = null
let historyListRequestSeq = 0
const historyDetailEpoch = createRequestEpoch()
let restoreCheckSeq = 0

const currentBatchLocalIndex = computed(() =>
  store.currentBatchPages.indexOf(store.currentPage!),
)
const canReorderBatch = computed(() => {
  if (expandedPages.value.length < 2) return false
  if (loadingBatchId.value !== null || isReordering.value) return false
  return !expandedPages.value.some((page) =>
    page.status === 'pending'
    || page.status === 'processing'
    || page.status === 'waiting',
  )
})

// A token identifies exactly one value copied from workspace state. Unlike a
// nextTick flag, it cannot suppress an unrelated user edit in the same flush.
let editorSyncGeneration = 0
let pendingExternalEditorSync: { generation: number; text: string } | null = null

function initialMeasureNumberKey(batchId: string | null): string {
  return `${initialMeasureNumberStorageKey}.${batchId || 'current'}`
}

function loadInitialMeasureNumber(batchId: string | null): number {
  const raw = Number.parseInt(localStorage.getItem(initialMeasureNumberKey(batchId)) || '', 10)
  return Number.isInteger(raw) && raw >= 1 ? raw : 1
}

watch(() => store.currentBatchId, (batchId) => {
  initialMeasureNumber.value = loadInitialMeasureNumber(batchId)
}, { immediate: true })
watch(initialMeasureNumber, (value) => {
  const normalized = typeof value === 'number' && Number.isInteger(value) && value >= 1
    ? value
    : 1
  if (value !== normalized) {
    initialMeasureNumber.value = normalized
    return
  }
  localStorage.setItem(
    initialMeasureNumberKey(store.currentBatchId),
    String(normalized),
  )
})

watch(() => store.currentBatchJianpuText, (v) => {
  if (v !== jianpuText.value) {
    const generation = ++editorSyncGeneration
    pendingExternalEditorSync = { generation, text: v }
    jianpuText.value = v
  }
}, { immediate: true })
watch(jianpuText, (v, previous) => {
  const isExternalSync = pendingExternalEditorSync?.text === v
  if (isExternalSync) pendingExternalEditorSync = null
  if (v !== store.currentBatchJianpuText) {
    const isUserEdit = !isExternalSync
    if (isUserEdit) updateTextAnchorsAfterEdit(previous ?? '', v)
    store.setBatchJianpuText(v, isUserEdit)
    if (isUserEdit) {
      store.setBatchRenderPageFileIds([])
      setFinalSvgFileIds([])
    }
    errorLine.value = -1
  }
})

function updateTextAnchorsAfterEdit(previous: string, current: string): void {
  const previousSections = parseJianpuPageSections(previous)
  const currentSections = parseJianpuPageSections(current)
  store.currentBatchPages.forEach((page, index) => {
    if (!page.textAnchors.length) return
    const previousSection = previousSections.find((section) => section.pageIndex === index)
      ?? previousSections[index]
    const currentSection = currentSections.find((section) => section.pageIndex === index)
      ?? currentSections[index]
    if (!previousSection || !currentSection) {
      store.patchPageById(page.id, {
        textAnchors: page.textAnchors.map((anchor) => ({ ...anchor, valid: false })),
      })
      return
    }
    const update = trackTextAnchors(previousSection.body, currentSection.body, page.textAnchors)
    store.patchPageById(page.id, { textAnchors: update.anchors })
  })
}

async function handleOriginalSourceClick(sourceId: string): Promise<void> {
  selectedSourceId.value = sourceId
  const candidates = store.textAnchors.filter((anchor) => anchor.source_id === sourceId)
  const sections = parseJianpuPageSections(jianpuText.value)
  const localIndex = Math.max(0, currentBatchLocalIndex.value)
  const currentSection = sections.find((item) => item.pageIndex === localIndex)
    ?? sections[localIndex]
  const range = sourceAnchorRange(
    candidates,
    currentSection?.body ?? store.currentPage?.jianpuText ?? '',
  )
  if (!range) {
    message.warning(
      candidates.length
        ? '对应简谱内容已被重构，无法精确定位'
        : '该识别元素在当前简谱中没有可定位目标',
    )
    return
  }

  if (!isViewingFinal.value) {
    const offset = currentSectionBodyOffset()
    if (!jianpuEditorRef.value?.selectRange(
      offset + range.start,
      offset + range.end,
    )) {
      message.warning('对应简谱范围当前不可见')
    }
    return
  }

  const scopedSourceId = `p${Math.max(0, currentBatchLocalIndex.value)}|${sourceId}`
  const targetPage = renderSourcePageLookup.value[scopedSourceId]
  if (targetPage !== undefined && targetPage !== finalRenderPageIndex.value) {
    finalRenderPageIndex.value = targetPage
    await nextTick()
  }
  const preview = svgPreviewRef.value
  const highlighted = preview
    ? await preview.highlightSource(scopedSourceId)
      || await preview.highlightSource(sourceId)
    : false
  if (!highlighted) {
    message.warning('当前渲染页中没有该元素，请重新渲染后再试')
  }
}

function currentSectionBodyOffset(): number {
  const sections = parseJianpuPageSections(jianpuText.value)
  const localIndex = Math.max(0, currentBatchLocalIndex.value)
  const section = sections.find((item) => item.pageIndex === localIndex) ?? sections[localIndex]
  if (!section?.markerLine) return 0
  const markerOffset = jianpuText.value.indexOf(section.markerLine)
  if (markerOffset < 0) return 0
  const bodyStart = markerOffset + section.markerLine.length
  return jianpuText.value[bodyStart] === '\n' ? bodyStart + 1 : bodyStart
}
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
watch(() => store.currentPage?.id ?? '', () => {
  entityLoadController?.abort()
  entityLoadController = null
  editMode.value = false
  correctableSheet.value = null
  deletedEntityIds.value = new Set(store.currentPage?.deletedSourceIds ?? [])
}, { immediate: true })
watch(currentNoteIndex, (index) => {
  if (!isViewingFinal.value || index < 0) return
  const ranges = renderPageNoteIndexRanges.value
  let targetPage: number | null = null
  if (ranges.length) {
    const pageIndex = ranges.findIndex(
      (range) =>
        range.start !== null
        && range.end !== null
        && index >= range.start
        && index <= range.end,
    )
    if (pageIndex >= 0) targetPage = pageIndex
  }
  if (targetPage === null) {
    targetPage = findNotePageIndex(jianpuText.value, index)
  }
  if (targetPage !== null && targetPage !== finalRenderPageIndex.value) {
    finalRenderPageIndex.value = targetPage
  }
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
  expandedBatchJianpuText.value = ''
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
      expandedBatchJianpuText.value = ''
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
    expandedBatchJianpuText.value = ''
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
      expandedPages.value = batch.pages
      expandedBatchJianpuText.value = batch.jianpu_text ?? ''
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

function handlePageDragStart(event: DragEvent, index: number): void {
  draggedPageIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function handlePageDragOver(index: number): void {
  dragOverIndex.value = index
}

function handlePageDrop(index: number): void {
  const from = draggedPageIndex.value
  draggedPageIndex.value = null
  dragOverIndex.value = null
  if (from === null || from === index) return
  void handleReorder(from, index)
}

function handlePageDragEnd(): void {
  draggedPageIndex.value = null
  dragOverIndex.value = null
}

async function handleReorder(fromIndex: number, toIndex: number): Promise<void> {
  const batchId = expandedBatchId.value
  if (!batchId) return

  const newPages = [...expandedPages.value]
  const [moved] = newPages.splice(fromIndex, 1)
  newPages.splice(toIndex, 0, moved)

  const pageSources = newPages.map((p) => ({
    inputFileName: p.input_file_name,
    jianpuText: p.jianpu_text,
  }))

  const restoredText = restoreJianpuPageText(expandedBatchJianpuText.value, pageSources)
  const sections = parseJianpuPageSections(restoredText)

  if (sections.length !== newPages.length) {
    message.error('页面数量与代码段数量不一致，无法排序')
    return
  }

  const [movedSection] = sections.splice(fromIndex, 1)
  sections.splice(toIndex, 0, movedSection)
  sections.forEach((section, i) => { section.pageIndex = i })

  const newBatchText = serializeJianpuPageSections(sections)
  const orderedPageIds = newPages.map((p) => p.id)
  const pageUpdates = sections.map((section) => ({
    jianpuText: section.body,
  }))

  isReordering.value = true
  try {
    const result = await requireData(historyApi.reorderPages(batchId, {
      jianpu_text: newBatchText,
      pages: orderedPageIds.map((pageId, i) => ({
        page_id: pageId,
        jianpu_text: pageUpdates[i]!.jianpuText,
      })),
    }))

    expandedPages.value = result.pages
    expandedBatchJianpuText.value = result.jianpu_text ?? newBatchText
    store.reorderBatchPages(batchId, orderedPageIds, pageUpdates, newBatchText)
    message.success('页面顺序已更新')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`排序失败：${msg}`)
    message.error(`排序失败：${msg}`)
    await refreshExpandedBatch(batchId, { clear: false, showLoading: false })
  } finally {
    isReordering.value = false
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
  let batchEngineVersion = ''
  let batchJianpuText = ''
  let renderPageOcrTexts: HistoryBatch['render_page_ocr_texts'] = []
  let pageIndex = allPages.findIndex((p) => p.id === page.id)
  try {
    const batch = await fetchStableHistoryBatch(batchId)
    if (!batch) return
    renderPageFileIds = batch.render_page_file_ids ?? []
    batchEngineVersion = batch.engine_version || ''
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
      overlayFileId: r.page.overlay_file_id || r.page.overlay_svg_file_id || '',
      sourceMapFileId: r.page.source_map_file_id ?? '',
      textHash: r.page.text_hash ?? '',
      textAnchors: r.page.text_anchors ?? [],
      textAttachments: r.page.text_attachments ?? [],
      svgFileIds: r.page.svg_file_id ? [r.page.svg_file_id] : [],
      taskId: r.page.task_id || '',
      status: r.page.status as TaskPageStatus,
      errorMessage: r.page.error_message,
      omrFileId: r.page.omr_file_id ?? '',
      originalMusicxml: r.page.original_musicxml ?? '',
      workingMusicxml: r.page.working_musicxml || r.page.original_musicxml || '',
      deletedSourceIds: r.page.deleted_source_ids ?? [],
      ...liveRecognitionTaskPatch(r.page.id, r.page.status),
    })),
    pageIndex >= 0 ? pageIndex : 0,
    renderPageFileIds,
    batchJianpuText,
    renderPageOcrTexts,
  )
  isViewingFinal.value = false
  if (!renderPageFileIds.length || batchEngineVersion !== 'publication-3') {
    try {
      renderPageFileIds = await renderFinalBatch()
    } catch (e: unknown) {
      const detail = e instanceof Error ? e.message : String(e)
      log.addError(`历史记录重新排版失败：${detail}`)
      message.error(`历史记录重新排版失败：${detail}`)
    }
  }
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
    .flatMap((entry) => [
      entry.input_file_id,
      entry.musicxml_file_id,
      entry.svg_file_id,
      entry.overlay_file_id,
      entry.source_map_file_id,
      entry.omr_file_id,
    ])
    .concat(renderPageFileIds)
    .filter((id): id is string => Boolean(id))
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
      if (entry.overlay_file_id && !exists[entry.overlay_file_id]) {
        patch.overlayFileId = ''
        warnings.push(`${entry.input_file_name}：原谱叠加层已失效`)
      }
      if (entry.source_map_file_id && !exists[entry.source_map_file_id]) {
        patch.sourceMapFileId = ''
        patch.textAnchors = []
        patch.deletedSourceIds = []
        warnings.push(`${entry.input_file_name}：原谱点击映射已失效`)
      }
      if (entry.omr_file_id && !exists[entry.omr_file_id]) {
        patch.omrFileId = ''
        patch.deletedSourceIds = []
        warnings.push(`${entry.input_file_name}：OMR 工程文件已失效`)
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

async function handleHistoryPageClick(page: HistoryPage): Promise<void> {
  await handleRestorePage(page)
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
      const filename = getExportFilename('mid')
      const result = page.jianpuText.trim()
        ? await requireData(exportApi.exportMidiText({
          jianpu_text: page.jianpuText,
          filename,
          title: '简谱',
          midi_tempo: settings.midiTempo,
        }))
        : await requireData(exportApi.exportMidi({
          musicxml_file_id: store.musicxmlFileId,
          filename,
          target_key: settings.targetKey,
          midi_tempo: settings.midiTempo,
        }))
      await finalizeExport({ fileId: result.file_id }, filename)
      log.addLog(`导出完成：${filename}`)
      message.success('导出完成')
      return
    }
    if (format === 'musicxml') {
      const page = currentExportPage()
      const filename = getExportFilename('musicxml')
      const result = page.jianpuText.trim()
        ? await requireData(exportApi.exportMusicXmlText({ jianpu_text: page.jianpuText, filename, title: '简谱' }))
        : await requireData(exportApi.exportMusicXml({
            musicxml_file_id: store.musicxmlFileId,
            filename,
            title: '简谱',
            target_key: settings.targetKey,
          }))
      await finalizeExport({ fileId: result.file_id }, filename)
      log.addLog(`导出完成：${filename}`)
      message.success('导出完成')
      return
    }
    if (format === 'png') {
      const ids = await renderExportSvgIds()
      const svgFileId = ids[Math.min(finalRenderPageIndex.value, ids.length - 1)]
      if (!svgFileId) throw new Error('暂无可导出的 A4 页面')
      const filename = getExportFilename('png')
      const result = await requireData(
        exportApi.exportRenderedImages([svgFileId], filename, 300, 'png'),
      )
      const exported = result.files[0]
      if (!exported) throw new Error('PNG 导出未生成文件')
      await finalizeExport({ fileId: exported.file_id }, exported.filename)
      log.addLog(`导出完成：${filename}`)
      message.success('导出完成')
      return
    }

    const svgIds = await renderExportSvgIds()
    if (!svgIds.length) throw new Error('暂无可导出的页面')
    const filename = getExportFilename('pdf')
    const result = await requireData(exportApi.exportRenderedPdf(svgIds, filename))
    await finalizeExport({ fileId: result.file_id }, filename)
    log.addLog(`导出完成：${filename}`)
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

async function downloadFile(fileId: string, filename: string): Promise<void> {
  const result = await fetchFileBlob(fileId)
  if (result.error) throw result.error
  downloadBlob(result.data, filename)
}

function getExportFilename(format: string): string {
  const base = store.currentBatchLabel
  switch (format) {
    case 'mid':
      return `${base}.mid`
    case 'musicxml':
      return `${base}.musicxml`
    case 'png':
      return `${base}.png`
    case 'pdf':
      return `${base}.pdf`
    default:
      return base
  }
}

type ExportSource =
  | { fileId: string }
  | { buffer: ArrayBuffer }

async function finalizeExport(source: ExportSource, filename: string): Promise<void> {
  const dir = settings.outputDir?.trim()
  const api = window.api
  if (!dir || !api.saveExportFile) {
    if ('fileId' in source) {
      await downloadFile(source.fileId, filename)
    } else {
      downloadBlob(new Blob([source.buffer]), filename)
    }
    return
  }

  let ipcSource: { buffer: ArrayBuffer }
  if ('fileId' in source) {
    const result = await fetchFileBlob(source.fileId)
    if (result.error) throw result.error
    ipcSource = { buffer: await result.data.arrayBuffer() }
  } else {
    ipcSource = source
  }

  const savedPath = await api.saveExportFile(ipcSource, dir, filename)
  message.success(`已保存到：${savedPath}`)
  if (api.openFolder) {
    await api.openFolder(dir)
  }
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
      sourceMapFileId: '',
      textAnchors: [],
      textAttachments: [],
      textHash: '',
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
  const result = await requireData(publicationRender.batchA4({
    pages,
    source_pages: buildBatchRenderSourcePages(),
    render_page_ocr_texts: currentRenderPageOcrTextsForRequest(),
    target_key: settings.targetKey,
    accidental_mode: settings.accidentalMode,
    measure_number_mode: settings.measureNumberMode,
    initial_measure_number: Math.max(1, Math.trunc(initialMeasureNumber.value || 1)),
    title: '简谱',
  }))
  const ids = renderResponsePageIds(result.pages, result.svg_file_id)
  await loadRenderSourcePageLookup(result.pages)
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

async function loadRenderSourcePageLookup(pages: RenderedSvgPage[]): Promise<void> {
  const lookup: Record<string, number> = {}
  await Promise.all((pages ?? []).map(async (page, index) => {
    if (!page.render_map_file_id) return
    const response = await fetchFileBlob(page.render_map_file_id)
    if (response.error) return
    try {
      const payload = JSON.parse(await response.data.text()) as {
        anchors?: Array<{ source_id?: string }>
      }
      for (const anchor of payload.anchors ?? []) {
        if (anchor.source_id) lookup[anchor.source_id] = index
      }
    } catch {
      // Invalid sidecars safely degrade to highlighting the current render page.
    }
  }))
  renderSourcePageLookup.value = lookup
  renderPageNoteIndexRanges.value = (pages ?? []).map((page) => ({
    start: page.note_index_start ?? null,
    end: page.note_index_end ?? null,
  }))
}

function buildBatchRenderPages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: jianpuText.value,
    title: '简谱',
  }).map((page, index) => ({
    ...page,
    text_anchors: store.currentBatchPages[index]?.textAnchors ?? [],
  }))
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
    store.setBatchRenderPageFileIds(updated.render_page_file_ids ?? [])
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

async function resetAll(): Promise<void> {
  store.setBusy(true)
  try {
    if (editMode.value) {
      editMode.value = false
    }
    deletedEntityIds.value = new Set()

    const result = await requireData(convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      page_image_file_id: store.originalFileId || undefined,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
    }))
    const split = splitJianpuAndOcr(result.jianpu_text)
    const page = store.currentPage
    if (page) {
      store.patchPageById(page.id, {
        jianpuText: split.jianpuText,
        textAnchors: result.text_anchors ?? [],
        textHash: result.text_hash ?? '',
        workingMusicxml: store.originalMusicxml,
        deletedSourceIds: [],
      })
      const nextBatchText = replaceJianpuSectionBody(
        jianpuText.value,
        Math.max(0, currentBatchLocalIndex.value),
        split.jianpuText,
        { inputFileName: page.inputFileName },
      )
      store.setBatchJianpuText(nextBatchText, false)
      await persistCorrectionState(page.id, nextBatchText)
    }
    store.setOcrText(split.ocrText || store.ocrText)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    log.addLog('已重置到识别初始状态')
    message.success('已重置')
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(`重置失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function toggleEditMode() {
  if (!canEditMarkers.value) return
  editMode.value = !editMode.value
  if (editMode.value && !correctableSheet.value) {
    await loadEntities()
  }
}

async function loadEntities(): Promise<void> {
  const pageId = store.currentPage?.id
  const omrFileId = store.omrFileId
  const sourceMapFileId = store.sourceMapFileId
  if (!pageId || !omrFileId || !sourceMapFileId) return
  entityLoadController?.abort()
  const controller = new AbortController()
  entityLoadController = controller
  const { data, error } = await correctApi.getEntities(
    omrFileId,
    sourceMapFileId,
    controller.signal,
  )
  if (controller.signal.aborted || store.currentPage?.id !== pageId) return
  entityLoadController = null
  if (error) {
    editMode.value = false
    message.error(error.message)
    return
  }
  const sheets = data.sheets ?? []
  if (sheets.length !== 1) {
    editMode.value = false
    message.warning(sheets.length ? '多页 OMR 暂不支持在单张原图上编辑标记' : '没有可安全定位的标记')
    return
  }
  correctableSheet.value = sheets[0] ?? null
}

function toggleEntityDelete(sourceId: string) {
  const next = new Set(deletedEntityIds.value)
  if (next.has(sourceId)) {
    next.delete(sourceId)
  } else {
    next.add(sourceId)
  }
  deletedEntityIds.value = next
}

async function applyCorrections(): Promise<void> {
  if (deletedEntityIds.value.size === 0) {
    message.info('未删除任何标记')
    return
  }
  const page = store.currentPage
  if (!page || !canEditMarkers.value) return
  applying.value = true
  try {
    const data = await requireData(correctApi.apply({
      original_musicxml: page.originalMusicxml,
      deleted_source_ids: [...deletedEntityIds.value],
      omr_file_id: page.omrFileId,
      source_map_file_id: page.sourceMapFileId,
      text_attachments: page.textAttachments,
      options: {
        target_key: settings.targetKey,
        accidental_mode: settings.accidentalMode,
        instrument_profile: 'general',
        title: page.textAttachments.find((item) => item.role === 'title')?.text || undefined,
        show_measure_numbers: settings.showMeasureNumbers,
        measure_number_mode: settings.measureNumberMode,
      },
    }))
    if (store.currentPage?.id !== page.id) {
      message.warning('页面已切换，本次修正结果未写入')
      return
    }
    const svgFileIds = data.svg_file_ids ?? []
    const nextBatchText = replaceJianpuSectionBody(
      jianpuText.value,
      Math.max(0, currentBatchLocalIndex.value),
      data.jianpu_text,
      { inputFileName: page.inputFileName },
    )
    store.patchPageById(page.id, {
      workingMusicxml: data.working_musicxml,
      jianpuText: data.jianpu_text,
      deletedSourceIds: [...deletedEntityIds.value],
      textAnchors: data.text_anchors ?? [],
      textHash: data.text_hash,
      svgFileId: svgFileIds[0] ?? '',
      svgFileIds,
    })
    store.setBatchJianpuText(nextBatchText, false)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    await persistCorrectionState(page.id, nextBatchText)
    message.success('修正已应用')
  } catch (e: unknown) {
    const detail = e instanceof Error ? e.message : String(e)
    log.addError(`应用标记修正失败：${detail}`)
    message.error(detail)
  } finally {
    applying.value = false
  }
}

async function persistCorrectionState(pageId: string, batchText: string): Promise<void> {
  const page = store.pages.find((entry) => entry.id === pageId)
  if (!page) return
  if (page.historyPageId) {
    const updated = await requireData(historyApi.updatePage(page.historyPageId, {
      jianpu_text: page.jianpuText,
      svg_file_id: page.svgFileId,
      text_hash: page.textHash,
      text_anchors: page.textAnchors,
      omr_file_id: page.omrFileId,
      original_musicxml: page.originalMusicxml,
      working_musicxml: page.workingMusicxml,
      deleted_source_ids: page.deletedSourceIds,
    }))
    replaceExpandedHistoryPage(updated)
  }
  if (page.historyBatchId) {
    await persistBatchJianpuText(page.historyBatchId, batchText)
  }
}

function transposeOctaveShift(direction: 1 | -1): void {
  const next = transposeOctave(jianpuText.value, direction)
  if (next === jianpuText.value) return
  jianpuText.value = next
  message.success(direction > 0 ? '已升高八度' : '已降低八度')
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

interface TextAttachmentUpdate {
  sourcePageIndex: number
  sourceAttachmentId: string
  text?: string
  fontSize?: number
  offsetX?: number
  offsetY?: number
  deleted?: boolean
}

function handleTextAttachmentUpdate(update: TextAttachmentUpdate): void {
  const page = store.currentBatchPages[update.sourcePageIndex]
  if (!page) return
  const target = page.textAttachments.find(
    (attachment) => attachment.id === update.sourceAttachmentId,
  )
  if (!target) return

  const textAttachments = update.deleted
    ? page.textAttachments.filter((attachment) => attachment.id !== target.id)
    : page.textAttachments.map((attachment) => {
      if (attachment.id !== target.id) return attachment
      return {
        ...attachment,
        text: update.text ?? attachment.text,
        font_size: update.fontSize ?? attachment.font_size,
        anchor: {
          ...attachment.anchor,
          offset_x: update.offsetX ?? attachment.anchor.offset_x,
          offset_y: update.offsetY ?? attachment.anchor.offset_y,
        },
      }
    })
  store.patchPageById(page.id, { textAttachments })
  store.setBatchRenderPageFileIds([])
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
    await requireData(publicationRender.normalizeJianpuText({ jianpu_text: savedJianpu, title: '简谱' }))
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
    overlay_file_id: store.currentPage?.overlayFileId || '',
    source_map_file_id: store.currentPage?.sourceMapFileId || '',
    text_hash: store.currentPage?.textHash || '',
    text_anchors: store.currentPage?.textAnchors || [],
    text_attachments: store.currentPage?.textAttachments || [],
    omr_file_id: store.currentPage?.omrFileId || '',
    original_musicxml: store.currentPage?.originalMusicxml || '',
    working_musicxml: store.currentPage?.workingMusicxml || '',
    deleted_source_ids: store.currentPage?.deletedSourceIds || [],
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
        overlay_file_id: page.overlayFileId,
        source_map_file_id: page.sourceMapFileId,
        text_hash: page.textHash,
        text_anchors: page.textAnchors,
        text_attachments: page.textAttachments,
        omr_file_id: page.omrFileId,
        original_musicxml: page.originalMusicxml,
        working_musicxml: page.workingMusicxml,
        deleted_source_ids: page.deletedSourceIds,
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
    })
    if (!page.historyPageId || page.historyPageId === currentHistoryPageId) continue
    const updated = await requireData(historyApi.updatePage(page.historyPageId, {
      jianpu_text: section.body,
    }))
    replaceExpandedHistoryPage(updated)
  }
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

.hist-page-item[draggable="true"] {
  cursor: grab;
}

.hist-page-item[draggable="true"]:active {
  cursor: grabbing;
}

.hist-page-dragging {
  opacity: 0.4;
}

.hist-page-drag-over {
  border-top: 2px solid var(--accent);
  padding-top: 2px;
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

.marker-edit-controls {
  display: flex;
  align-items: center;
  gap: 6px;
}

.deleted-count {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: none;
  letter-spacing: 0;
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
