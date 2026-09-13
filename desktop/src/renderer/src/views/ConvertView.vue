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
          <n-button size="small" :type="liveRenderEnabled ? 'primary' : 'default'" @click="toggleLiveRender">即时渲染</n-button>
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
          <n-popover
            trigger="click"
            placement="bottom"
            :show="snapshotHistoryOpen"
            :disabled="!canOpenSnapshotHistory"
            @update:show="handleSnapshotHistoryShow"
          >
            <template #trigger>
              <n-button
                size="small"
                type="primary"
                :disabled="store.isBusy || !canOpenSnapshotHistory"
              >
                历史版本
              </n-button>
            </template>
            <div class="snapshot-list">
              <div class="snapshot-hint">
                默认保存最近三次的历史
              </div>
              <div
                v-if="snapshotLoading"
                class="snapshot-empty"
              >
                加载中…
              </div>
              <div
                v-else-if="!snapshotList.length"
                class="snapshot-empty"
              >
                暂无历史版本
              </div>
              <template v-else>
                <div
                  v-for="snapshot in snapshotList"
                  :key="snapshot.id"
                  class="snapshot-item"
                >
                  <span
                    class="snapshot-source"
                    :class="snapshot.source"
                  >{{ snapshotSourceLabel(snapshot.source) }}</span>
                  <span class="snapshot-time">{{ formatSnapshotTime(snapshot.created_at) }}</span>
                  <n-button
                    size="tiny"
                    quaternary
                    type="primary"
                    @click="restoreJianpuSnapshot(snapshot)"
                  >
                    恢复
                  </n-button>
                </div>
              </template>
            </div>
          </n-popover>
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
            style="width: 120px"
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
                :type="editMode ? 'default' : 'primary'"
                @click="editMode ? cancelEditMode() : enterEditMode()"
              >
                {{ editMode ? '取消' : '删除标记' }}
              </n-button>
              <template v-if="editMode">
                <span class="deleted-count">已删除 {{ deletedEntityIds.size }}</span>
                <n-button
                  size="tiny"
                  type="warning"
                  :loading="applying"
                  :disabled="loadingEntities"
                  @click="applyCorrections"
                >
                  应用
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
              :mapped-source-ids="mappedSourceIds"
              :selected-source-id="selectedSourceId"
              :editable="editMode"
              :entities="correctableEntities"
              :deleted-entity-ids="deletedEntityIds"
              :applied-deleted-source-ids="appliedDeletedSourceIds"
              :entity-width="correctableSheet?.width"
              :entity-height="correctableSheet?.height"
              @select-source="handleOriginalSourceClick"
              @toggle-delete="toggleEntityDelete"
            />
          </div>
        </div>

        <div class="ws-panel ws-right">
          <div class="ws-panel-head">
            <span class="panel-head-label">
              <span>{{ isViewingFinal ? '最终渲染' : '简谱编辑' }}</span>
              <span
                v-if="store.currentBatchHasUnsavedChanges"
                class="unsaved-hint"
              >当前有更改未保存</span>
            </span>
            <div class="panel-head-actions">
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal || editorTransposing"
                @click="transposeOctaveShift(1)"
              >
                升八度
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal || editorTransposing"
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
                :disabled="store.isBusy || !canRenderCurrentScore || editorTransposing"
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
              :playback-group-index="currentPlaybackGroupIndex"
              :playback-position="playbackPosition"
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
            <div v-else class="jianpu-live-layout" :style="{ gridTemplateRows: `${liveEditorRatio}% 14px minmax(0, 1fr)` }">
              <div class="jianpu-live-editor"><jianpu-editor
              ref="jianpuEditorRef"
              v-model="jianpuText"
              :current-note-index="currentNoteIndex"
              :initial-measure-number="initialMeasureNumber"
              :syntax-highlight="settings.jianpuSyntaxHighlight"
              :syntax-diagnostics="syntaxStore.visibleDiagnostics"
              :active-diagnostic-id="syntaxStore.activeId"
              :error-line="errorLine"
              :flash-line="flashLine"
              :scroll-persistence-key="store.currentBatchId"
              :structure-markers-enabled="store.currentBatchId !== null"
              @update:initial-measure-number="initialMeasureNumber = $event"
              @rekey-applied="handleRekeyApplied"
              @cursor-change="liveCursorTick++"
            /></div>
              <div class="jianpu-live-divider" @mousedown="startLiveResize" title="调整上下区域高度" />
              <LiveJianpuPreview :svg="livePreviewSvg" :loading="livePreviewLoading" :error="livePreviewError" />
            </div>
          </div>
        </div>
      </div>
      <jianpu-player
        :musicxml-file-id="store.musicxmlFileId"
        :jianpu-text="operationalJianpuText"
        :session-key="store.currentBatchId"
        @update:current-note-index="currentNoteIndex = $event"
        @update:playback-group-index="currentPlaybackGroupIndex = $event"
        @update:playback-position="playbackPosition = $event"
      />
    </div>
    <n-modal
      v-model:show="discardConfirmVisible"
      preset="card"
      :style="{ width: 'min(440px, calc(100vw - 48px))' }"
      title="有更改尚未保存"
      :bordered="false"
      :mask-closable="false"
      :closable="false"
      @esc="settleDiscardConfirmation(false)"
    >
      <p class="discard-confirm-copy">
        当前有更改未保存，{{ discardConfirmAction }}将丢弃这些修改，是否继续？
      </p>
      <template #footer>
        <div class="discard-confirm-actions">
          <n-button @click="settleDiscardConfirmation(false)">
            取消
          </n-button>
          <n-button
            type="warning"
            @click="settleDiscardConfirmation(true)"
          >
            继续
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useWorkspaceStore } from '../stores/workspace'
import { useSettingsStore } from '../stores/settings'
import {
  isRenderLayoutStale,
  PUBLICATION_ENGINE_VERSION,
} from '../utils/jianpuLayout'
import { useLogStore } from '../stores/log'
import { useSyntaxDiagnosticsStore } from '../stores/syntaxDiagnostics'
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
  JianpuSnapshotItem,
  RenderedSvgPage,
  SheetEntitiesDTO,
} from '../models/types'
import type { TaskPage, TaskPageStatus } from '../stores/workspace'
import JianpuEditor from '../components/JianpuEditor.vue'
import JianpuPlayer from '../components/JianpuPlayer.vue'
import type { SyntaxDiagnostic } from '../models/types'
import OriginalPreview from '../components/OriginalPreview.vue'
import PublicationPreview from '../components/PublicationPreview.vue'
import LiveJianpuPreview from '../components/LiveJianpuPreview.vue'
import { renderApi } from '../api/render'
import { loadRenderPageIndex, saveRenderPageIndex } from '../composables/useViewPersistence'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { isRenderAborted } from '../utils/renderAbort'
import {
  hasJianpuPageMarkers,
  ensureRecognizedPageTempoHeader,
  ensureRecognizedTempoHeader,
  parseJianpuPageSections,
  jianpuPageSectionBodyOffset,
  maskJianpuStructureMarkers,
  replaceJianpuSectionBody,
  restoreJianpuPageText,
  serializeJianpuPageSections,
} from '../utils/jianpuPageSections'
import {
  hashJianpuText,
  hasJianpuTextEdits,
  preserveEditedJianpuText,
} from '../utils/jianpuTextState'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import { createRequestEpoch } from '../utils/asyncCoordination'
import {
  reconcileRekeyedTextAnchors,
  reconcileTextAnchors,
  type RekeySpanMapping,
} from '../utils/textAnchorTracking'
import { readPlaybackRange, playbackPage, type PlaybackRange } from '../utils/playbackNavigation'
import { sanitizeSvg } from '../utils/svgSanitizer'
import { sourceAnchorRange } from '../utils/sourceAnchorSelection'
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
  notifyHistoryUpdated,
  type HistoryPagePatchDetail,
} from '../utils/historyEvents'
import { createWorkspacePersistence } from '../utils/workspacePersistence'
import {
  ImageOutline,
  ChevronBackOutline,
  ChevronForwardOutline,
  CloudDownloadOutline,
  TimeOutline,
  RefreshOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { NButton, NPopover, NSelect, NIcon, NModal, NPopconfirm, useMessage } from 'naive-ui'

const store = useWorkspaceStore()
const settings = useSettingsStore()
const publicationRender = usePublicationRender()
const livePreviewSvg = ref("")
const livePreviewError = ref("")
const livePreviewLoading = ref(false)
const liveRenderEnabled = ref(true)
const liveEditorRatio = ref(Number(localStorage.getItem("score-trans.live-editor-ratio") || 50))
let livePreviewTimer: ReturnType<typeof setTimeout> | null = null
let livePreviewController: AbortController | null = null
const liveCursorTick = ref(0)
function currentMeasureText(text: string): string {
  const pos = jianpuEditorRef.value?.getSelectionRange()?.start ?? text.length
  const left = text.lastIndexOf("|", Math.max(0, pos - 1)) + 1
  const rightBar = text.indexOf("|", pos)
  const right = rightBar >= 0 ? rightBar + 1 : text.length
  const segment = text.slice(left, right).trim()
  return segment || text
}
let liveResizeStart: { y: number; ratio: number; height: number } | null = null
const log = useLogStore()
const syntaxStore = useSyntaxDiagnosticsStore()
const message = useMessage()
const workspacePersistence = createWorkspacePersistence(historyApi, notifyHistoryUpdated)
const discardConfirmVisible = ref(false)
const discardConfirmAction = ref<'重置' | '恢复历史版本'>('重置')
let discardConfirmResolver: ((value: boolean) => void) | null = null
const jianpuEditorRef = ref<{
  selectRange: (
    start: number,
    end: number,
    options?: { flash?: boolean },
  ) => boolean
  getSelectionRange: () => { start: number; end: number } | null
  flushPendingAutoTranspose: () => Promise<void>
  transposing: boolean
} | null>(null)
interface RekeyAppliedPayload {
  before: string
  after: string
  anchorMapping: RekeySpanMapping[] | null
}
const pendingRekeyApplied = ref<RekeyAppliedPayload | null>(null)
const editorTransposing = computed(() => jianpuEditorRef.value?.transposing ?? false)
const svgPreviewRef = ref<{
  highlightSource: (sourceId: string) => Promise<boolean>
} | null>(null)
const selectedSourceId = ref('')
const editMode = ref(false)
const deletedEntityIds = ref<Set<string>>(new Set())
const appliedDeletedSourceIds = computed(() => store.currentPage?.deletedSourceIds ?? [])
const correctableSheet = ref<SheetEntitiesDTO | null>(null)
const correctableEntities = computed<CorrectableEntityDTO[]>(
  () => correctableSheet.value?.entities ?? [],
)
const applying = ref(false)
const loadingEntities = ref(false)
let entityLoadController: AbortController | null = null

const canEditMarkers = computed(() => (
  !!store.omrFileId
  && !!store.sourceMapFileId
  && !!store.originalMusicxml
  && /\.(png|jpe?g|tiff?|webp)$/i.test(store.originalFileName)
))

const renderSourcePageLookup = ref<Record<string, number>>({})
const renderPlaybackRanges = ref<Array<PlaybackRange | null>>([])
const clickableSourceIds = computed(() => {
  if (isViewingFinal.value && !finalSvgFileId.value) return []
  return [...new Set(
    store.textAnchors
      .filter((anchor) => anchor.valid !== false)
      .map((anchor) => anchor.source_id),
  )]
})
const mappedSourceIds = computed(() => {
  if (isViewingFinal.value && !finalSvgFileId.value) return []
  return [...new Set(
    (store.currentPage?.textAnchorBaselineAnchors ?? [])
      .map((anchor) => anchor.source_id),
  )]
})

const jianpuText = ref(store.currentBatchJianpuText)
const operationalJianpuText = computed(() => (
  store.currentBatchId === null
    ? maskJianpuStructureMarkers(jianpuText.value)
    : jianpuText.value
))
const hasJianpuText = computed(() => jianpuText.value.trim().length > 0)
const currentNoteIndex = ref(-1)
const currentPlaybackGroupIndex = ref(-1)
const playbackPosition = ref({ tick: -1, onsetTick: -1, ppq: 480 })
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

const snapshotHistoryOpen = ref(false)
const snapshotList = ref<JianpuSnapshotItem[]>([])
const snapshotLoading = ref(false)
const canOpenSnapshotHistory = computed(() => currentHistoryBatchId() !== null)

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

watch([jianpuText, liveCursorTick], ([text]) => {

  if (livePreviewTimer) clearTimeout(livePreviewTimer)
  livePreviewTimer = setTimeout(async () => {
    if (!text.trim()) { livePreviewSvg.value = ""; livePreviewError.value = ""; return }
    livePreviewController?.abort(); livePreviewController = new AbortController(); livePreviewLoading.value = true
    const result = await renderApi.liveJianpuSvg({ jianpu_text: currentMeasureText(text), show_measure_numbers: false, initial_measure_number: initialMeasureNumber.value }, livePreviewController.signal)
    if (result.data) { livePreviewSvg.value = result.data.svg; livePreviewError.value = "" }
    else if (result.error && result.error.name !== "AbortError") livePreviewError.value = result.error.message
    livePreviewLoading.value = false
  }, 150)
})
function toggleLiveRender(): void {`r`n  liveRenderEnabled.value = !liveRenderEnabled.value`r`n  if (!liveRenderEnabled.value) { livePreviewController?.abort(); if (livePreviewTimer) clearTimeout(livePreviewTimer); livePreviewLoading.value = false }`r`n}`r`nfunction startLiveResize(event: MouseEvent): void {
  const target = event.currentTarget as HTMLElement
  const parent = target.parentElement
  if (!parent) return
  liveResizeStart = { y: event.clientY, ratio: liveEditorRatio.value, height: parent.clientHeight }
  const move = (e: MouseEvent) => { if (!liveResizeStart) return; const next = liveResizeStart.ratio + ((e.clientY-liveResizeStart.y)/liveResizeStart.height)*100; liveEditorRatio.value = Math.max(20, Math.min(80, next)) }
  const up = () => { localStorage.setItem("score-trans.live-editor-ratio", String(liveEditorRatio.value)); liveResizeStart=null; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up) }
  window.addEventListener("mousemove", move); window.addEventListener("mouseup", up)
}

watch(() => store.currentBatchId, (batchId) => {
  syntaxStore.clear()
  initialMeasureNumber.value = loadInitialMeasureNumber(batchId)
  syntaxStore.schedule(operationalJianpuText.value)
}, { immediate: true })
watch(initialMeasureNumber, (value) => {
  const normalized = typeof value === 'number' && Number.isInteger(value) && value >= 1
    ? value
    : 1
  if (value !== normalized) {
    initialMeasureNumber.value = normalized
    return
  }
  // 与当前批次已持久化的值一致说明是批次切换/初始化加载，不是用户修改，
  // 此时不能让已有渲染失效。
  const changed = loadInitialMeasureNumber(store.currentBatchId) !== normalized
  localStorage.setItem(
    initialMeasureNumberKey(store.currentBatchId),
    String(normalized),
  )
  if (changed) {
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
  }
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
  if (isExternalSync) pendingRekeyApplied.value = null
  const rekey = pendingRekeyApplied.value
  const isRekeySync = !!rekey
    && rekey.before === previous
    && rekey.after === v
  if (isRekeySync) pendingRekeyApplied.value = null
  if (v !== store.currentBatchJianpuText) {
    const isUserEdit = !isExternalSync && !isRekeySync
    const shouldMarkDirty = !isExternalSync
    if (isRekeySync && rekey) {
      updateTextAnchorsAfterRekey(rekey)
    } else if (isUserEdit) {
      updateTextAnchorsAfterEdit(previous ?? '', v)
    }
    store.setBatchJianpuText(v, shouldMarkDirty)
    if (isUserEdit || isRekeySync) {
      store.setBatchRenderPageFileIds([])
      setFinalSvgFileIds([])
    }
    errorLine.value = -1
  }
  syntaxStore.schedule(operationalJianpuText.value)
}, { immediate: true })

function handleRekeyApplied(payload: RekeyAppliedPayload): void {
  pendingRekeyApplied.value = payload
}

watch(() => settings.jianpuMeasureDurationCheck, () => {
  syntaxStore.schedule(operationalJianpuText.value)
})

watch(() => syntaxStore.selectionVersion, () => {
  const diagnostic = syntaxStore.activeId
    ? syntaxStore.diagnostics.find((item) => item.id === syntaxStore.activeId)
    : undefined
  if (diagnostic) selectSyntaxDiagnostic(diagnostic)
})

function selectSyntaxDiagnostic(diagnostic: SyntaxDiagnostic): void {
  jianpuEditorRef.value?.selectRange(diagnostic.start, diagnostic.end)
}

function updateTextAnchorsAfterEdit(previous: string, current: string): void {
  if (store.currentBatchId === null) return
  let previousSections
  let currentSections
  try {
    previousSections = parseJianpuPageSections(previous)
    currentSections = parseJianpuPageSections(current)
  } catch {
    store.currentBatchPages.forEach((page) => {
      store.patchPageById(page.id, {
        textAnchors: page.textAnchors.map((anchor) => ({ ...anchor, valid: false })),
      })
    })
    return
  }
  store.currentBatchPages.forEach((page, index) => {
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
    if (!page.textAnchorBaselineAnchors.length) return
    if (previousSection.body === currentSection.body) return
    const update = reconcileTextAnchors(
      page.textAnchorBaselineText,
      currentSection.body,
      page.textAnchorBaselineAnchors,
      page.textAnchors,
    )
    store.patchPageById(page.id, { textAnchors: update.anchors })
  })
}

function updateTextAnchorsAfterRekey(payload: RekeyAppliedPayload): void {
  if (store.currentBatchId === null) return
  const mappings = payload.anchorMapping
  if (!mappings?.length) {
    updateTextAnchorsAfterEdit(payload.before, payload.after)
    refreshRekeyBaselines(payload.after)
    return
  }

  let beforeSections
  let afterSections
  try {
    beforeSections = parseJianpuPageSections(payload.before)
    afterSections = parseJianpuPageSections(payload.after)
  } catch {
    updateTextAnchorsAfterEdit(payload.before, payload.after)
    refreshRekeyBaselines(payload.after)
    return
  }

  store.currentBatchPages.forEach((page, index) => {
    const beforeSection = beforeSections.find((section) => section.pageIndex === index)
      ?? beforeSections[index]
    const afterSection = afterSections.find((section) => section.pageIndex === index)
      ?? afterSections[index]
    if (!beforeSection || !afterSection) {
      store.patchPageById(page.id, {
        textAnchors: page.textAnchors.map((anchor) => ({ ...anchor, valid: false })),
      })
      return
    }

    const beforeOffset = jianpuPageSectionBodyOffset(
      payload.before,
      beforeSections,
      beforeSections.indexOf(beforeSection),
    )
    const afterOffset = jianpuPageSectionBodyOffset(
      payload.after,
      afterSections,
      afterSections.indexOf(afterSection),
    )
    const globalAnchors = page.textAnchors.map((anchor) => ({
      ...anchor,
      start_utf16: anchor.start_utf16 + beforeOffset,
      end_utf16: anchor.end_utf16 + beforeOffset,
    }))
    const update = reconcileRekeyedTextAnchors(globalAnchors, mappings)
    const localAnchors = update.anchors.map((anchor) => ({
      ...anchor,
      start_utf16: Math.max(0, anchor.start_utf16 - afterOffset),
      end_utf16: Math.max(0, anchor.end_utf16 - afterOffset),
    }))
    store.patchPageById(page.id, {
      textAnchors: localAnchors,
      textAnchorBaselineText: afterSection.body,
      textAnchorBaselineAnchors: localAnchors.map((anchor) => ({ ...anchor })),
    })
  })
}

function refreshRekeyBaselines(text: string): void {
  if (store.currentBatchId === null) return
  let sections
  try {
    sections = parseJianpuPageSections(text)
  } catch {
    return
  }
  store.currentBatchPages.forEach((page, index) => {
    const section = sections.find((item) => item.pageIndex === index) ?? sections[index]
    if (!section) return
    store.patchPageById(page.id, {
      textAnchorBaselineText: section.body,
      textAnchorBaselineAnchors: page.textAnchors.map((anchor) => ({ ...anchor })),
    })
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

function currentPageJianpuText(text = jianpuText.value): string {
  const sections = parseJianpuPageSections(text)
  const localIndex = Math.max(0, currentBatchLocalIndex.value)
  const section = sections.find((item) => item.pageIndex === localIndex) ?? sections[localIndex]
  return section?.body ?? store.currentPage?.jianpuText ?? text
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
watch(finalRenderPageIndex, (index) => {
  if (isViewingFinal.value && store.currentBatchId) {
    saveRenderPageIndex(store.currentBatchId, index)
  }
})
watch(() => store.currentPage?.id ?? '', () => {
  entityLoadController?.abort()
  entityLoadController = null
  editMode.value = false
  correctableSheet.value = null
  deletedEntityIds.value = new Set(store.currentPage?.deletedSourceIds ?? [])
}, { immediate: true })
watch([playbackPosition, renderPlaybackRanges, isViewingFinal], () => {
  if (!isViewingFinal.value) return
  const target = playbackPage(renderPlaybackRanges.value, playbackPosition.value)
  if (target !== null && target !== finalRenderPageIndex.value) {
    finalRenderPageIndex.value = target
  }
})

// Rebuild from the rendered SVGs, including restored history. Ranges are tied
// to this exact file list; responses for a superseded render cannot replace it.
watch(finalSvgFileIds, async (ids, _previous, onCleanup) => {
  let cancelled = false
  const controller = new AbortController()
  onCleanup(() => { cancelled = true; controller.abort() })
  renderPlaybackRanges.value = []
  const ranges = await Promise.all(ids.map(async (id) => {
    try {
      const response = await fetchFileBlob(id, controller.signal)
      if (response.error) return null
      return readPlaybackRange(sanitizeSvg(await response.data.text()))
    } catch { return null }
  }))
  if (!cancelled) renderPlaybackRanges.value = ranges
}, { immediate: true })

onMounted(() => {
  if (!settings.loaded) void settings.load()
  loadHistory()
  stopHistoryUpdatedListener = listenHistoryUpdated(() => loadHistory(false, { refreshExpanded: false }))
  stopHistoryPagePatchedListener = listenHistoryPagePatched(handleHistoryPagePatched)
})

onUnmounted(() => {
  settleDiscardConfirmation(false)
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
  store.markAllHistoryBatchesDeleted()
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
    store.markHistoryBatchDeleted(batchId)
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

  if (!(await persistUnsavedBeforeReplace('恢复历史版本'))) return

  let allPages = expandedPages.value
  let renderPageFileIds: string[] = []
  let batchEngineVersion = ''
  let batchJianpuText = ''
  let renderPageOcrTexts: HistoryBatch['render_page_ocr_texts'] = []
  let renderOutputStale = false
  let renderLayoutKey = ''
  let pageIndex = allPages.findIndex((p) => p.id === page.id)
  try {
    const batch = await fetchStableHistoryBatch(batchId)
    if (!batch) return
    renderPageFileIds = batch.render_page_file_ids ?? []
    batchEngineVersion = batch.engine_version || ''
    batchJianpuText = batch.jianpu_text || ''
    renderPageOcrTexts = batch.render_page_ocr_texts || []
    renderOutputStale = batch.render_output_stale ?? false
    renderLayoutKey = batch.render_layout_key ?? ''
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
    const hasTextAnchorBaseline = p.text_anchor_baseline_text !== undefined
      && p.text_anchor_baseline_anchors !== undefined
    return { page: p, split, jianpu: split.jianpuText, hasTextAnchorBaseline }
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
      textAnchorBaselineText: r.hasTextAnchorBaseline
        ? r.page.text_anchor_baseline_text
        : r.jianpu,
      textAnchorBaselineAnchors: r.hasTextAnchorBaseline
        ? r.page.text_anchor_baseline_anchors
        : (r.page.text_anchors ?? []),
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
    renderOutputStale,
    renderLayoutKey,
  )
  isViewingFinal.value = false
  await nextTick()
  if (
    !renderPageFileIds.length
    || batchEngineVersion !== PUBLICATION_ENGINE_VERSION
    || renderOutputStale
    || isRenderLayoutStale(renderLayoutKey, settings.jianpuLayoutKey)
  ) {
    try {
      renderPageFileIds = await renderFinalBatch()
    } catch (e: unknown) {
      if (isRenderAborted(e)) return
      if (handleJianpuOutputBlocked('重新渲染历史记录', e)) return
      const detail = e instanceof Error ? e.message : String(e)
      log.addError(`历史记录重新排版失败：${detail}`)
      message.error(`历史记录重新排版失败：${detail}`)
      return
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

  const sections = parseJianpuPageSections(operationalJianpuText.value)
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

function isSyntaxValidationError(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'jianpu_syntax'
}

function handleJianpuOutputBlocked(action: string, error: unknown): boolean {
  if (!isSyntaxValidationError(error)) return false
  const raw = error instanceof Error ? error.message : String(error)
  errorLine.value = extractErrorLineFromMessage(raw)
  log.addError(`${action}失败：存在语法错误，无法${action}`)
  message.error(`存在语法错误，无法${action}，请先修复`)
  return true
}

async function exportScore(): Promise<void> {
  store.setBusy(true)
  errorLine.value = -1
  try {
    const format = exportFormat.value
    if (format === 'mid') {
      const filename = getExportFilename('mid')
      const batchText = operationalJianpuText.value
      const musicxmlFileIds = store.currentBatchPages.map((page) => page.musicxmlFileId).filter(Boolean)
      const result = batchText.trim()
        ? await requireData(exportApi.exportMidiText({ jianpu_text: batchText, filename, title: '简谱' }))
        : await requireData(exportApi.exportMidi({
          musicxml_file_id: musicxmlFileIds[0] || store.musicxmlFileId,
          musicxml_file_ids: musicxmlFileIds.length ? musicxmlFileIds : undefined,
          filename,
          target_key: settings.targetKey,
        }))
      await finalizeExport({ fileId: result.file_id }, filename)
      log.addLog(`导出完成：${filename}`)
      message.success('导出完成')
      return
    }
    if (format === 'musicxml') {
      const filename = getExportFilename('musicxml')
      const batchText = operationalJianpuText.value
      const musicxmlFileIds = store.currentBatchPages.map((page) => page.musicxmlFileId).filter(Boolean)
      const result = batchText.trim()
        ? await requireData(exportApi.exportMusicXmlText({ jianpu_text: batchText, filename, title: '简谱' }))
        : await requireData(exportApi.exportMusicXml({
            musicxml_file_id: musicxmlFileIds[0] || store.musicxmlFileId,
            musicxml_file_ids: musicxmlFileIds.length ? musicxmlFileIds : undefined,
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
    if (isRenderAborted(e)) return
    const raw = e instanceof Error ? e.message : String(e)
    if (handleJianpuOutputBlocked('导出', e)) return
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
    jianpuText: operationalJianpuText.value,
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
  if (
    store.currentBatchRenderOutputStale
    || isRenderLayoutStale(
      store.currentBatchRenderLayoutKey,
      settings.jianpuLayoutKey,
    )
  ) return renderFinalBatch()
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
    ...settings.jianpuLayoutRequest,
  }))
  const ids = renderResponsePageIds(result.pages, result.svg_file_id)
  const layoutKey = result.pages[0]?.layout_key || settings.jianpuLayoutKey
  await loadRenderSourcePageLookup(result.pages)
  setFinalSvgFileIds(ids)
  store.setBatchRenderPageFileIds(ids, undefined, layoutKey)
  store.setBatchRenderPageOcrTexts(
    renderResponsePageOcrTexts(result.pages),
    false,
  )
  store.markBatchRenderPageOcrClean()
  const batchId = store.currentBatchId
  if (batchId) {
    try {
      await workspacePersistence.saveRenderState(store, batchId, {
        renderPageFileIds: ids,
        renderPageOcrTexts: store.currentBatchRenderPageOcrTextEntries(),
        renderOutputStale: false,
        renderLayoutKey: layoutKey,
      })
    } catch (error: unknown) {
      log.addLog(
        `保存连续 A4 渲染状态失败：${error instanceof Error ? error.message : String(error)}`,
        'warn',
      )
    }
  }
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

}

function buildBatchRenderPages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: operationalJianpuText.value,
    title: '简谱',
  })
}

function buildBatchRenderSourcePages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: operationalJianpuText.value,
    title: '简谱',
  })
}

function currentRenderPageOcrTextsForRequest() {
  return renderPageOcrTextsForRequest(
    store.currentBatchRenderPageOcrTextEntries(),
    store.currentBatchRenderOutputStale,
  )
}

function currentPageSvgIds(): string[] {
  return store.svgFileIds.length ? store.svgFileIds : (store.svgFileId ? [store.svgFileId] : [])
}

function currentHistoryBatchId(): number | null {
  return store.currentBatchPages.find((page) => page.historyBatchId)?.historyBatchId ?? null
}

function setFinalSvgFileIds(ids: string[]): void {
  finalSvgFileIds.value = [...ids]
  finalRenderPageIndex.value = Math.max(
    0,
    Math.min(finalRenderPageIndex.value, finalSvgFileIds.value.length - 1),
  )
}

async function resetAll(): Promise<void> {
  if (!(await confirmDiscardUnsaved('重置'))) return
  store.setBusy(true)
  try {
    if (editMode.value) {
      editMode.value = false
    }
    deletedEntityIds.value = new Set()

    const result = await requireData(convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
    }))
    const split = splitJianpuAndOcr(result.jianpu_text)
    const pageIndex = Math.max(0, currentBatchLocalIndex.value)
    const resetJianpuText = ensureRecognizedPageTempoHeader(
      split.jianpuText,
      pageIndex,
    )
    const alignment = reconcileTextAnchors(
      result.jianpu_text,
      resetJianpuText,
      result.text_anchors ?? [],
    )
    const textAnchorBaselineAnchors = alignment.reconciled
      ? alignment.anchors
      : (result.text_anchors ?? []).map((anchor) => ({ ...anchor, valid: false }))
    const page = store.currentPage
    if (page) {
      const pagePatch: Partial<TaskPage> = {
        jianpuText: resetJianpuText,
        jianpuDirty: false,
        ocrText: '',
        textAttachments: [],
        textAnchors: textAnchorBaselineAnchors.map((anchor) => ({ ...anchor })),
        textAnchorBaselineText: resetJianpuText,
        textAnchorBaselineAnchors,
        textHash: await hashJianpuText(resetJianpuText),
        workingMusicxml: store.originalMusicxml,
        deletedSourceIds: [],
      }
      const nextBatchText = ensureRecognizedTempoHeader(
        replaceJianpuSectionBody(
          jianpuText.value,
          pageIndex,
          resetJianpuText,
          { inputFileName: page.inputFileName },
        ),
      )
      if (page.batchId) {
        await workspacePersistence.saveBatch(store, page.batchId, 'reset', {
          pages: store.currentBatchPages.map((entry) =>
            entry.id === page.id ? { ...entry, ...pagePatch } : entry,
          ),
          jianpuText: nextBatchText,
          renderPageFileIds: [],
          renderPageOcrTexts: [],
          renderOutputStale: true,
          renderLayoutKey: '',
        })
      }
      store.patchPageById(page.id, pagePatch)
      store.setBatchJianpuText(nextBatchText, false)
    }
    store.setOcrText('')
    store.setBatchRenderPageFileIds([])
    store.setBatchRenderPageOcrTexts([], true)
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

async function enterEditMode() {
  if (!canEditMarkers.value) return
  editMode.value = true
  if (!correctableSheet.value) {
    loadingEntities.value = true
    try {
      await loadEntities()
    } finally {
      loadingEntities.value = false
    }
  }
}

function cancelEditMode() {
  entityLoadController?.abort()
  entityLoadController = null
  editMode.value = false
  deletedEntityIds.value = new Set(store.currentPage?.deletedSourceIds ?? [])
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
    message.warning(sheets.length ? '多页 OMR 暂不支持在单张原图上删除标记' : '没有可安全定位的标记')
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
  const page = store.currentPage
  if (!page || !canEditMarkers.value) return
  const baseline = new Set(page.deletedSourceIds ?? [])
  const current = deletedEntityIds.value
  const hasPendingChange =
    [...current].some((id) => !baseline.has(id)) ||
    [...baseline].some((id) => !current.has(id))
  if (!hasPendingChange) {
    message.info('没有未应用的改动')
    return
  }
  const editedPageText = currentPageJianpuText()
  const preserveEditedText = await hasJianpuTextEdits(
    editedPageText,
    page.textAnchorBaselineText,
    page.textHash,
    page.jianpuDirty,
  )
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
        ...settings.jianpuLayoutRequest,
      },
    }))
    if (store.currentPage?.id !== page.id) {
      message.warning('页面已切换，本次修正结果未写入')
      return
    }
    const svgFileIds = data.svg_file_ids ?? []
    const corrected = splitJianpuAndOcr(data.jianpu_text)
    const alignment = reconcileTextAnchors(
      data.jianpu_text,
      corrected.jianpuText,
      data.text_anchors ?? [],
    )
    const textAnchorBaselineAnchors = alignment.reconciled
      ? alignment.anchors
      : (data.text_anchors ?? []).map((anchor) => ({ ...anchor, valid: false }))
    const textHash = await hashJianpuText(corrected.jianpuText)
    const nextPageText = preserveEditedJianpuText(
      editedPageText,
      corrected.jianpuText,
      preserveEditedText,
      page.textAnchorBaselineText,
    )
    const nextTextAnchors = reconcileTextAnchors(
      corrected.jianpuText,
      nextPageText,
      textAnchorBaselineAnchors,
      page.textAnchors,
    ).anchors
    const nextBatchText = replaceJianpuSectionBody(
      jianpuText.value,
      Math.max(0, currentBatchLocalIndex.value),
      nextPageText,
      { inputFileName: page.inputFileName },
    )
    const nextSvgFileIds = preserveEditedText ? [] : svgFileIds
    const pagePatch: Partial<TaskPage> = {
      workingMusicxml: data.working_musicxml,
      jianpuText: nextPageText,
      jianpuDirty: preserveEditedText,
      deletedSourceIds: [...deletedEntityIds.value],
      textAnchors: nextTextAnchors,
      textAnchorBaselineText: corrected.jianpuText,
      textAnchorBaselineAnchors,
      // Hash the same canonical text used by the baseline anchors so restored
      // manual edits are compared against one consistent reference.
      textHash,
      svgFileId: nextSvgFileIds[0] ?? '',
      svgFileIds: nextSvgFileIds,
    }
    await workspacePersistence.saveBatch(store, page.batchId, 'save', {
      pages: store.currentBatchPages.map((entry) =>
        entry.id === page.id ? { ...entry, ...pagePatch } : entry,
      ),
      jianpuText: nextBatchText,
      renderPageFileIds: [],
      renderOutputStale: true,
      renderLayoutKey: '',
    })
    store.patchPageById(page.id, pagePatch)
    store.setBatchJianpuText(nextBatchText, false)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    message.success('修正已应用')
    editMode.value = false
  } catch (e: unknown) {
    const detail = e instanceof Error ? e.message : String(e)
    log.addError(`应用标记修正失败：${detail}`)
    message.error(detail)
  } finally {
    applying.value = false
  }
}

function transposeOctaveShift(direction: 1 | -1): void {
  const sel = jianpuEditorRef.value?.getSelectionRange()
  const hasRange = !!sel && sel.end > sel.start
  let next: string
  let reveal: { start: number; end: number } | null = null
  if (hasRange) {
    const sub = jianpuText.value.slice(sel!.start, sel!.end)
    const transposed = transposeOctave(sub, direction)
    next =
      jianpuText.value.slice(0, sel!.start)
      + transposed
      + jianpuText.value.slice(sel!.end)
    reveal = { start: sel!.start, end: sel!.start + transposed.length }
  } else {
    next = transposeOctave(jianpuText.value, direction)
  }
  if (next === jianpuText.value) return
  jianpuText.value = next
  if (reveal) {
    nextTick(() =>
      jianpuEditorRef.value?.selectRange(reveal.start, reveal.end, { flash: false }),
    )
  }
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
    const batchId = store.currentBatchId
    if (!batchId) throw new Error('暂无可保存批次')
    await workspacePersistence.saveBatch(store, batchId)
    log.addLog('已保存 OMR、简谱和 OCR 信息')
    message.success('已保存')
  } catch (e: unknown) {
    if (isRenderAborted(e)) return
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
  store.markBatchAttachmentUserEdited(page.batchId)
  store.setBatchRenderPageFileIds([])
}

async function toggleFinalView(): Promise<void> {
  if (isViewingFinal.value) { isViewingFinal.value = false; return }
  isRenderingFinal.value = true
  store.setBusy(true)
  errorLine.value = -1
  try {
    await renderExportSvgIds()
    const savedPage = loadRenderPageIndex(store.currentBatchId)
    if (
      savedPage != null
      && savedPage >= 0
      && savedPage < finalSvgFileIds.value.length
      && savedPage !== finalRenderPageIndex.value
    ) {
      finalRenderPageIndex.value = savedPage
    }
    isViewingFinal.value = true
  } catch (e: unknown) {
    if (isRenderAborted(e)) return
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    if (handleJianpuOutputBlocked('渲染', e)) return
    errorLine.value = extractErrorLineFromMessage(msg)
    log.addError(`渲染失败：${msg}`)
    message.error(msg)
  } finally {
    store.setBusy(false)
    isRenderingFinal.value = false
  }
}

async function loadJianpuSnapshots(): Promise<void> {
  const batchId = currentHistoryBatchId()
  if (!batchId) {
    snapshotList.value = []
    return
  }
  snapshotLoading.value = true
  try {
    const { data, error } = await historyApi.listJianpuSnapshots(batchId)
    if (error) {
      snapshotList.value = []
      message.error(error.message)
      return
    }
    snapshotList.value = data
  } finally {
    snapshotLoading.value = false
  }
}

function handleSnapshotHistoryShow(show: boolean): void {
  snapshotHistoryOpen.value = show
  if (show) void loadJianpuSnapshots()
}

function formatSnapshotTime(createdAt: string): string {
  return createdAt.slice(5, 16)
}

function snapshotSourceLabel(source: string): string {
  if (source === 'reset') return '重置'
  if (source === 'auto') return '自动'
  return '保存'
}

async function restoreJianpuSnapshot(snapshot: JianpuSnapshotItem): Promise<void> {
  if (!(await confirmDiscardUnsaved('恢复历史版本'))) return
  const text = snapshot.jianpu_text
  isViewingFinal.value = false
  store.setBatchJianpuText(text, false)
  const sections = parseJianpuPageSections(text)
  store.currentBatchPages.forEach((page, index) => {
    const section = sections.find((item) => item.pageIndex === index) ?? sections[index]
    if (!section) {
      store.patchPageById(page.id, {
        textAnchors: page.textAnchors.map((anchor) => ({ ...anchor, valid: false })),
      })
      return
    }
    const update = reconcileTextAnchors(
      page.textAnchorBaselineText,
      section.body,
      page.textAnchorBaselineAnchors,
      page.textAnchors,
    )
    store.patchPageById(page.id, {
      jianpuText: section.body,
      textAnchors: update.anchors,
    })
  })
  // 恢复的快照作为当前简谱的干净状态，不清除 OCR 或附件的未保存修改。
  store.markBatchJianpuClean()
  store.setBatchRenderPageFileIds([])
  setFinalSvgFileIds([])
  snapshotHistoryOpen.value = false
  const label = snapshotSourceLabel(snapshot.source)
  const time = formatSnapshotTime(snapshot.created_at)
  log.addLog(`已恢复历史版本（${label} ${time}）`)
  message.success(`已恢复到${label}版本 ${time}`)
}

function confirmDiscardUnsaved(action: '重置' | '恢复历史版本'): Promise<boolean> {
  if (!store.currentBatchHasUnsavedChanges) return Promise.resolve(true)
  settleDiscardConfirmation(false)
  discardConfirmAction.value = action
  discardConfirmVisible.value = true
  return new Promise((resolve) => {
    discardConfirmResolver = resolve
  })
}

function settleDiscardConfirmation(value: boolean): void {
  const resolve = discardConfirmResolver
  discardConfirmResolver = null
  discardConfirmVisible.value = false
  resolve?.(value)
}

// 保存前把编辑器里待执行的异步写入兑现，避免它们落进 saveBatch 的 await 窗口
// 而把批次重新标脏。见 App.vue 的 saveAndClose。
async function flushPendingEdits(): Promise<void> {
  await jianpuEditorRef.value?.flushPendingAutoTranspose()
}

// loadBatch 会整页替换当前批次。切走前先保存仍有历史目标的编辑；没有本地批次
// 或历史目标已被删除时保留现场，等目标成功加载后再随工作区替换一起丢弃。
async function persistUnsavedBeforeReplace(action: string): Promise<boolean> {
  store.setBusy(true)
  try {
    await flushPendingEdits()
    if (!store.hasUnsavedChanges) return true
    const result = await workspacePersistence.saveAllUnsavedBatches(store, {
      mode: 'discard',
    })
    if (result.savedBatchIds.length) {
      log.addLog(`${action}前已自动保存当前批次的未保存更改`)
    }
    return true
  } catch (e: unknown) {
    if (isRenderAborted(e)) return false
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`自动保存失败，已取消${action}：${msg}`)
    message.error(`保存当前更改失败，已取消${action}：${msg}`)
    return false
  } finally {
    store.setBusy(false)
  }
}

defineExpose({ flushPendingEdits })

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

.jianpu-live-layout { height:100%; min-height:0; display:grid; gap:0; }
.jianpu-live-editor { min-height:0; overflow:hidden; }
.jianpu-live-divider { cursor:row-resize; background:var(--border-color); position:relative; border-top:1px solid var(--text-tertiary); border-bottom:1px solid var(--text-tertiary); }
.jianpu-live-divider::before { content:""; position:absolute; left:calc(50% - 24px); top:4px; width:48px; height:4px; border-radius:4px; background:var(--text-tertiary); box-shadow:0 7px 0 var(--text-tertiary); }
.jianpu-live-divider:hover { background:var(--primary-color); }

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

.panel-head-label {
  display: inline-flex;
  align-items: center;
  gap: 12px;
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

.snapshot-list {
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.snapshot-hint {
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-soft);
  color: var(--text-tertiary);
  font-size: 10px;
}

.snapshot-empty {
  padding: 8px 4px;
  color: var(--text-tertiary);
  font-size: 11px;
  text-align: center;
}

.snapshot-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.snapshot-source {
  flex-shrink: 0;
  width: 28px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--border-soft);
  color: var(--text-tertiary);
  font-size: 10px;
}

.snapshot-source.reset {
  background: rgba(240, 160, 32, 0.16);
  color: var(--warning);
}

.snapshot-time {
  flex: 1;
  color: var(--text-secondary);
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

.unsaved-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--warning);
  font-size: 10px;
  white-space: nowrap;
}

.unsaved-hint::before {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  content: '';
}

.discard-confirm-copy {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.discard-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
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

