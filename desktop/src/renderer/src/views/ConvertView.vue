<template>
  <div class="workspace">
    <div :class="['ws-history', { open: historyOpen }]">
      <div class="ws-hist-head">
        <span class="ws-hist-title">{{ t('convert.history.title') }}</span>
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
            {{ t('convert.history.confirmDeleteAll') }}
          </n-popconfirm>
        </div>
      </div>
      <div class="ws-hist-body">
        <div
          v-if="!histLoading && !histBatches.length"
          class="hist-empty"
        >
          <span>{{ t('convert.history.empty') }}</span>
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
            <span class="hist-batch-name">{{ batch.first_file_name || t('convert.history.unknown') }}</span>
            <span
              v-if="batch.page_count > 1"
              class="hist-batch-count"
            >{{ t('convert.history.pageCount', { count: batch.page_count }) }}</span>
            <n-popconfirm
              :show-icon="false"
              @positive-click="handleDeleteBatch(batch.id)"
            >
              <template #trigger>
                <button
                  class="hist-delete"
                  type="button"
                  :title="t('convert.history.deleteTitle')"
                  @click.stop
                >
                  <n-icon size="12">
                    <TrashOutline />
                  </n-icon>
                </button>
              </template>
              {{ t('convert.history.confirmDeleteBatch') }}
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
              {{ t('convert.history.loading') }}
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
              <span class="hist-page-name">{{ page.input_file_name || t('convert.history.pageN', { n: pi + 1 }) }}</span>
              <span
                v-if="page.status === 'unrecognized'"
                class="hist-unrecognized-label"
              >{{ t('convert.history.unrecognized') }}</span>
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
            :title="t('convert.history.toggleTitle')"
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
          <n-button size="small" :type="liveRenderEnabled ? 'primary' : 'default'" @click="toggleLiveRender">{{ t('convert.toolbar.liveRender') }}</n-button>
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
                {{ t('convert.toolbar.snapshots') }}
              </n-button>
            </template>
            <div class="snapshot-list">
              <div class="snapshot-hint">
                {{ t('convert.snapshot.hint') }}
              </div>
              <div
                v-if="snapshotLoading"
                class="snapshot-empty"
              >
                {{ t('convert.snapshot.loading') }}
              </div>
              <div
                v-else-if="!snapshotList.length"
                class="snapshot-empty"
              >
                {{ t('convert.snapshot.empty') }}
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
                    {{ t('convert.snapshot.restore') }}
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
            {{ t('convert.toolbar.reset') }}
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
            {{ t('convert.toolbar.export') }}
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
            <span class="panel-head-title">{{ t('convert.panel.originalStaff') }}</span>
            <span
              v-if="store.originalFileName"
              class="panel-filename"
            >{{ store.originalFileName }}</span>
            <div
              v-if="canOpenMarkerEditor"
              class="marker-edit-controls"
            >
              <n-button
                size="tiny"
                :secondary="!editMode"
                :type="editMode ? 'default' : 'primary'"
                @click="editMode ? cancelEditMode() : enterEditMode()"
              >
                {{ editMode ? t('common.action.cancel') : t('convert.marker.deleteMark') }}
              </n-button>
              <template v-if="editMode">
                <span class="edited-count">{{ t('convert.marker.editedCount', { count: editedCount }) }}</span>
                <n-button
                  size="tiny"
                  type="primary"
                  :loading="applying"
                  :disabled="loadingEntities || !canEditMarkers"
                  :title="store.originalMusicxml ? undefined : t('convert.marker.missingMusicxml')"
                  @click="applyCorrections()"
                >
                  <template #icon>
                    <n-icon><CheckmarkOutline /></n-icon>
                  </template>
                  {{ t('convert.marker.apply') }}
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
              :busy="applying"
              :selected-source-id="selectedSourceId"
              :editable="editMode"
              :entities="correctableEntities"
              :applied-candidate-selections="effectiveCandidateSelections"
              :suspicious-glyphs="correctableSheet?.suspicious_glyphs"
              :selected-glyph-id="selectedGlyphId"
              :deleted-entity-ids="deletedEntityIds"
              :applied-deleted-source-ids="appliedDeletedSourceIds"
              :entity-width="correctableSheet?.width"
              :entity-height="correctableSheet?.height"
              @select-source="handleOriginalSourceClick"
              @toggle-delete="toggleEntityDelete"
              @select-glyph="selectSuspiciousGlyph"
            >
              <template #marker-editor="{ close }">
                <MarkerInspector
                  v-if="editMode && selectedEntity"
                  mode="entity"
                  :tag="selectedEntity.tag"
                  :shape="selectedEntity.shape"
                  :original-shape="selectedEntity.shape"
                  :selected-shape="selectedCandidateShape"
                  :current-score="selectedEntityDisplayGrade"
                  :candidates="selectedEntityCandidates"
                  :disabled="applying"
                  @select="selectCandidate(selectedEntity.source_id, $event)"
                  @close="close"
                />
                <MarkerInspector
                  v-else-if="editMode && selectedGlyph"
                  mode="glyph"
                  :tag="selectedGlyph.tag"
                  :shape="selectedGlyph.shape || 'UNKNOWN'"
                  :original-shape="selectedGlyph.shape || ''"
                  :selected-shape="selectedCandidateShape"
                  :current-score="selectedEntityDisplayGrade"
                  :candidates="selectedGlyphCandidates"
                  :disabled="applying"
                  @select="selectCandidate(selectedGlyph.glyph_id, $event)"
                  @close="close"
                />
              </template>
            </original-preview>
          </div>
        </div>

        <div class="ws-panel ws-right">
          <div class="ws-panel-head">
            <span class="panel-head-label">
              <span>{{ isViewingFinal ? t('convert.panel.finalRender') : t('convert.panel.jianpuEdit') }}</span>
              <span
                v-if="store.currentBatchHasUnsavedChanges"
                class="unsaved-hint"
              >{{ t('convert.panel.unsavedHint') }}</span>
            </span>
            <div class="panel-head-actions">
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal || editorTransposing"
                @click="transposeOctaveShift(1)"
              >
                {{ t('convert.editor.octaveUp') }}
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :disabled="!hasJianpuText || isViewingFinal || editorTransposing"
                @click="transposeOctaveShift(-1)"
              >
                {{ t('convert.editor.octaveDown') }}
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
                {{ t('convert.editor.mergeRecognition') }}
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :loading="store.isBusy"
                :disabled="store.isBusy || !canSaveCurrentPage"
                @click="saveJianpu"
              >
                {{ t('common.action.save') }}
              </n-button>
              <n-button
                size="tiny"
                quaternary
                :loading="isRenderingFinal"
                :disabled="store.isBusy || !canRenderCurrentScore || editorTransposing"
                @click="toggleFinalView"
              >
                {{ isViewingFinal ? t('common.action.edit') : t('convert.toolbar.render') }}
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
              :playback-position="renderPlaybackPosition"
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
              <span>{{ t('convert.panel.noRender') }}</span>
            </div>
            <div v-else class="jianpu-live-layout" :style="liveRenderEnabled ? { gridTemplateRows: `${liveEditorRatio}% 10px minmax(0, 1fr)` } : { gridTemplateRows: '1fr' }">
              <div class="jianpu-live-editor"><jianpu-editor
              ref="jianpuEditorRef"
              v-model="jianpuText"
              :playback-highlight="playbackHighlight"
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
              <template v-if="liveRenderEnabled">
                <div class="jianpu-live-divider" :title="t('convert.editor.resizeTitle')" @mousedown="startLiveResize" />
                <LiveJianpuPreview :svg="livePreviewSvg" :loading="livePreviewLoading" :error="livePreviewError" :warnings="livePreviewWarnings" />
              </template>
            </div>
          </div>
        </div>
      </div>
      <jianpu-player
        :musicxml-file-id="store.musicxmlFileId"
        :jianpu-text="operationalJianpuText"
        :session-key="store.currentBatchId"
        @update:playback-highlight="playbackHighlight = $event"
        @update:current-note-index="currentNoteIndex = $event"
        @update:playback-group-index="currentPlaybackGroupIndex = $event"
        @update:playback-position="playbackPosition = $event"
      />
    </div>
    <n-modal
      v-model:show="discardConfirmVisible"
      preset="card"
      :style="{ width: 'min(440px, calc(100vw - 48px))' }"
      :title="t('convert.discard.title')"
      :bordered="false"
      :mask-closable="false"
      :closable="false"
      @esc="settleDiscardConfirmation(false)"
    >
      <p class="discard-confirm-copy">
        {{ t('convert.discard.body', { action: discardActionLabel }) }}
      </p>
      <template #footer>
        <div class="discard-confirm-actions">
          <n-button @click="settleDiscardConfirmation(false)">
            {{ t('common.action.cancel') }}
          </n-button>
          <n-button
            type="warning"
            @click="settleDiscardConfirmation(true)"
          >
            {{ t('common.action.continue') }}
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
import { emptyPlaybackHighlight, type PlaybackHighlight } from '../utils/midiSourceMap'
import type { SyntaxDiagnostic } from '../models/types'
import OriginalPreview from '../components/OriginalPreview.vue'
import MarkerInspector from '../components/MarkerInspector.vue'
import PublicationPreview from '../components/PublicationPreview.vue'
import LiveJianpuPreview from '../components/LiveJianpuPreview.vue'
import { useLiveJianpuPreview } from '../composables/useLiveJianpuPreview'
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
  CheckmarkOutline,
  CloudDownloadOutline,
  TimeOutline,
  RefreshOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { NButton, NPopover, NSelect, NIcon, NModal, NPopconfirm, useMessage } from 'naive-ui'
import { t } from '../i18n'

const store = useWorkspaceStore()
const settings = useSettingsStore()
const publicationRender = usePublicationRender()
const livePreview = useLiveJianpuPreview()
const { svg: livePreviewSvg, error: livePreviewError, warnings: livePreviewWarnings, loading: livePreviewLoading } = livePreview
const liveRenderEnabled = ref(true)
const liveEditorRatio = ref(Number(localStorage.getItem("score-trans.live-editor-ratio") || 50))
const liveCursorTick = ref(0)
let liveResizeStart: { y: number; ratio: number; height: number } | null = null
const log = useLogStore()
const syntaxStore = useSyntaxDiagnosticsStore()
const message = useMessage()
const workspacePersistence = createWorkspacePersistence(historyApi, notifyHistoryUpdated)
const discardConfirmVisible = ref(false)
const discardConfirmAction = ref<'reset' | 'restore'>('reset')
let discardConfirmResolver: ((value: boolean) => void) | null = null

type ConvertAction = 'reset' | 'restore' | 'export' | 'render' | 'historyRender'
function actionLabel(action: ConvertAction): string {
  return t(`convert.action.${action}`)
}
const discardActionLabel = computed(() =>
  discardConfirmAction.value === 'reset'
    ? t('convert.discard.actionReset')
    : t('convert.discard.actionRestore'),
)
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
const candidateSelections = ref<Record<string, string>>({})
const effectiveCandidateSelections = computed(() => {
  const selections: Record<string, string> = {}
  for (const [sourceId, shape] of Object.entries(candidateSelections.value)) {
    const entity = correctableEntities.value.find((item) => item.source_id === sourceId)
    const glyph = correctableSheet.value?.suspicious_glyphs?.find((item) => item.glyph_id === sourceId)
    const candidate = entity?.candidates?.find((item) => item.shape === shape)
      ?? glyph?.candidates?.find((item) => item.shape === shape)
    if (candidate && (entity || glyph)) {
      selections[sourceId] = shape
    }
  }
  return selections
})
const selectedGlyphId = ref('')
const selectedGlyph = computed(() => correctableSheet.value?.suspicious_glyphs?.find(
  (glyph) => glyph.glyph_id === selectedGlyphId.value,
))
const selectedEntityCandidates = computed(() => (
  (selectedEntity.value?.candidates ?? selectedGlyph.value?.candidates ?? []).slice(0, 5)
))
const selectedGlyphCandidates = computed(() => (
  selectedGlyph.value?.candidates?.slice(0, 5) ?? []
))
const appliedDeletedSourceIds = computed(() => store.currentPage?.deletedSourceIds ?? [])
const correctableSheet = ref<SheetEntitiesDTO | null>(null)
const correctableEntities = computed<CorrectableEntityDTO[]>(
  () => correctableSheet.value?.entities ?? [],
)
const selectedEntity = computed(() => correctableEntities.value.find(
  (entity) => entity.source_id === selectedSourceId.value,
))
const selectedCandidateShape = computed(() => selectedEntity.value
  ? candidateSelections.value[selectedEntity.value.source_id] ?? selectedEntity.value.shape
  : selectedGlyph.value
    ? candidateSelections.value[selectedGlyph.value.glyph_id] ?? ''
    : '')
const selectedEntityDisplayGrade = computed(() => {
  const selectedShape = selectedCandidateShape.value
  return selectedEntity.value?.candidates?.find((candidate) => candidate.shape === selectedShape)?.score
    ?? selectedEntity.value?.grade
    ?? selectedGlyph.value?.candidates?.find((candidate) => candidate.shape === selectedShape)?.score
    ?? selectedGlyph.value?.grade
    ?? 0
})
const applying = ref(false)
const loadingEntities = ref(false)
let entityLoadController: AbortController | null = null

const canEditMarkers = computed(() => (
  !!store.omrFileId
  && !!store.sourceMapFileId
  && !!store.originalMusicxml
  && /\.(png|jpe?g|tiff?|webp)$/i.test(store.originalFileName)
))
const canLoadMarkerData = computed(() => !!store.omrFileId && !!store.sourceMapFileId)
const canOpenMarkerEditor = computed(() => (
  !!store.originalFileId
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
const playbackHighlight = ref<PlaybackHighlight>(emptyPlaybackHighlight())
const playbackPosition = ref({ tick: -1, onsetTick: -1, ppq: 480 })
const renderPlaybackPosition = computed(() => store.currentBatchRenderOutputStale
  ? { tick: -1, onsetTick: -1, ppq: 480 }
  : playbackPosition.value)
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

watch(
  [jianpuText, liveCursorTick, liveRenderEnabled, initialMeasureNumber, () => store.currentBatchId, () => settings.jianpuBreakBeamsAtBeat],
  ([text, , enabled, initialNumber, documentId]) => {
    const cursorOffset = jianpuEditorRef.value?.getSelectionRange()?.start ?? text.length
    livePreview.update({
      documentId,
      enabled,
      request: { jianpu_text: text, cursor_offset: cursorOffset, show_measure_numbers: false, initial_measure_number: initialNumber, jianpu_break_beams_at_beat: settings.jianpuBreakBeamsAtBeat },
    })
  },
)
function toggleLiveRender(): void {
  liveRenderEnabled.value = !liveRenderEnabled.value
}
function startLiveResize(event: MouseEvent): void {
  event.preventDefault()
  const target = event.currentTarget as HTMLElement
  const parent = target.parentElement
  if (!parent) return
  liveResizeStart = { y: event.clientY, ratio: liveEditorRatio.value, height: parent.clientHeight }
  document.body.classList.add("live-resizing")
  const move = (e: MouseEvent) => { if (!liveResizeStart) return; const next = liveResizeStart.ratio + ((e.clientY-liveResizeStart.y)/liveResizeStart.height)*100; liveEditorRatio.value = Math.max(20, Math.min(80, next)) }
  const up = () => { localStorage.setItem("score-trans.live-editor-ratio", String(liveEditorRatio.value)); liveResizeStart=null; document.body.classList.remove("live-resizing"); window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up) }
  window.addEventListener("mousemove", move); window.addEventListener("mouseup", up)
}

watch(() => store.currentBatchId, (batchId) => {
  syntaxStore.clear()
  errorLine.value = -1
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
  selectedGlyphId.value = ''
  if (editMode.value) return
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
        ? t('convert.message.rangeRebuilt')
        : t('convert.message.elementNoTarget'),
    )
    return
  }

  if (!isViewingFinal.value) {
    const offset = currentSectionBodyOffset()
    if (!jianpuEditorRef.value?.selectRange(
      offset + range.start,
      offset + range.end,
    )) {
      message.warning(t('convert.message.rangeNotVisible'))
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
    message.warning(t('convert.message.elementNotInRender'))
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
  if (!isViewingFinal.value) flashCurrentPageSection(t('convert.log.sourceSwitchPage'))
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
watch([renderPlaybackPosition, renderPlaybackRanges, isViewingFinal], () => {
  if (!isViewingFinal.value) return
  const target = playbackPage(renderPlaybackRanges.value, renderPlaybackPosition.value)
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
  livePreview.dispose()
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
      log.addError(t('convert.history.loadFailed', { msg: e instanceof Error ? e.message : String(e) }))
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
  message.success(t('convert.history.cleared'))
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
    message.success(t('convert.history.deleted'))
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(t('convert.history.deleteFailed', { msg }))
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
      log.addError(t('convert.history.detailLoadFailed', { msg: e instanceof Error ? e.message : String(e) }))
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
    message.error(t('convert.history.orderMismatch'))
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
    message.success(t('convert.history.orderUpdated'))
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(t('convert.history.sortFailed', { msg }))
    message.error(t('convert.history.sortFailed', { msg }))
    await refreshExpandedBatch(batchId, { clear: false, showLoading: false })
  } finally {
    isReordering.value = false
  }
}

async function handleRestorePage(page: HistoryPage): Promise<void> {
  if (store.isBusy) {
    message.warning(t('convert.history.recognizingRestore'))
    return
  }

  const batchId = expandedBatchId.value
  if (!batchId) return

  if (!(await persistUnsavedBeforeReplace('restore'))) return

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
    log.addError(t('convert.history.refreshDetailFailed', { msg: e instanceof Error ? e.message : String(e) }))
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
      recognitionCandidateSelections: r.page.recognition_candidate_selections ?? {},
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
      if (handleJianpuOutputBlocked('historyRender', e)) return
      const detail = e instanceof Error ? e.message : String(e)
      log.addError(t('convert.history.relayoutFailed', { detail }))
      message.error(t('convert.history.relayoutFailed', { detail }))
      return
    }
  }
  void validateRestoredBatchFiles(allPages, renderPageFileIds)
  void nextTick(() => flashCurrentPageSection(t('convert.log.sourceHistoryRestore')))

  message.success(t('convert.history.restored', { count: allPages.length }))
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
  message.info(t('convert.history.updatingRetry'))
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
        warnings.push(`${entry.input_file_name}: ${t('convert.history.fileInvalid')}`)
      }
      if (entry.musicxml_file_id && !exists[entry.musicxml_file_id]) {
        patch.musicxmlFileId = ''
        warnings.push(`${entry.input_file_name}: ${t('convert.history.musicxmlInvalid')}`)
      }
      if (entry.svg_file_id && !exists[entry.svg_file_id]) {
        patch.svgFileId = ''
        patch.svgFileIds = []
        warnings.push(`${entry.input_file_name}: ${t('convert.history.svgInvalid')}`)
      }
      if (entry.overlay_file_id && !exists[entry.overlay_file_id]) {
        patch.overlayFileId = ''
        warnings.push(`${entry.input_file_name}: ${t('convert.history.overlayInvalid')}`)
      }
      if (entry.source_map_file_id && !exists[entry.source_map_file_id]) {
        patch.sourceMapFileId = ''
        patch.textAnchors = []
        patch.deletedSourceIds = []
        warnings.push(`${entry.input_file_name}: ${t('convert.history.clickmapInvalid')}`)
      }
      if (entry.omr_file_id && !exists[entry.omr_file_id]) {
        patch.omrFileId = ''
        patch.deletedSourceIds = []
        warnings.push(`${entry.input_file_name}: ${t('convert.history.omrInvalid')}`)
      }
      if (Object.keys(patch).length) {
        store.patchPageByHistoryPageId(entry.id, patch)
      }
    }
    if (warnings.length) {
      log.addLog(t('convert.history.partialInvalid', { warnings: warnings.join(', ') }), 'warn')
      message.warning(t('convert.history.partialInvalidMsg', { warnings: warnings.join('; ') }))
    }
  } catch (e: unknown) {
    if (seq === restoreCheckSeq) {
      log.addLog(t('convert.history.validateFailed', { msg: e instanceof Error ? e.message : String(e) }), 'warn')
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
  return t('convert.message.musicxmlStale')
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

function handleJianpuOutputBlocked(action: ConvertAction, error: unknown): boolean {
  if (!isSyntaxValidationError(error)) return false
  const raw = error instanceof Error ? error.message : String(error)
  errorLine.value = extractErrorLineFromMessage(raw)
  const label = actionLabel(action)
  log.addError(t('convert.message.syntaxBlockLog', { action: label }))
  message.error(t('convert.message.syntaxBlockMsg', { action: label }))
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
        ? await requireData(exportApi.exportMidiText({ jianpu_text: batchText, filename, title: t('convert.exportTitle') }))
        : await requireData(exportApi.exportMidi({
          musicxml_file_id: musicxmlFileIds[0] || store.musicxmlFileId,
          musicxml_file_ids: musicxmlFileIds.length ? musicxmlFileIds : undefined,
          filename,
          target_key: settings.targetKey,
        }))
      await finalizeExport({ fileId: result.file_id }, filename)
      log.addLog(t('convert.message.exportDoneLog', { filename }))
      message.success(t('convert.message.exportDone'))
      return
    }
    if (format === 'musicxml') {
      const filename = getExportFilename('musicxml')
      const batchText = operationalJianpuText.value
      const musicxmlFileIds = store.currentBatchPages.map((page) => page.musicxmlFileId).filter(Boolean)
      const result = batchText.trim()
        ? await requireData(exportApi.exportMusicXmlText({ jianpu_text: batchText, filename, title: t('convert.exportTitle') }))
        : await requireData(exportApi.exportMusicXml({
            musicxml_file_id: musicxmlFileIds[0] || store.musicxmlFileId,
            musicxml_file_ids: musicxmlFileIds.length ? musicxmlFileIds : undefined,
            filename,
            title: t('convert.exportTitle'),
            target_key: settings.targetKey,
          }))
      await finalizeExport({ fileId: result.file_id }, filename)
      log.addLog(t('convert.message.exportDoneLog', { filename }))
      message.success(t('convert.message.exportDone'))
      return
    }
    if (format === 'png') {
      const ids = await renderExportSvgIds()
      const svgFileId = ids[Math.min(finalRenderPageIndex.value, ids.length - 1)]
      if (!svgFileId) throw new Error(t('convert.message.noExportPage'))
      const filename = getExportFilename('png')
      const result = await requireData(
        exportApi.exportRenderedImages([svgFileId], filename, 300, 'png'),
      )
      const exported = result.files[0]
      if (!exported) throw new Error(t('convert.message.pngNoFile'))
      await finalizeExport({ fileId: exported.file_id }, exported.filename)
      log.addLog(t('convert.message.exportDoneLog', { filename }))
      message.success(t('convert.message.exportDone'))
      return
    }

    const svgIds = await renderExportSvgIds()
    if (!svgIds.length) throw new Error(t('convert.message.noPage'))
    const filename = getExportFilename('pdf')
    const result = await requireData(exportApi.exportRenderedPdf(svgIds, filename))
    await finalizeExport({ fileId: result.file_id }, filename)
    log.addLog(t('convert.message.exportDoneLog', { filename }))
    message.success(t('convert.message.exportDone'))
  } catch (e: unknown) {
    if (isRenderAborted(e)) return
    const raw = e instanceof Error ? e.message : String(e)
    if (handleJianpuOutputBlocked('export', e)) return
    errorLine.value = extractErrorLineFromMessage(raw)
    log.addError(t('convert.message.exportFailed', { msg: raw }))
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
  message.success(t('convert.message.savedTo', { path: savedPath }))
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
      t('convert.log.sectionMismatch', { source, pages: batchPages.length, sections: sections.length }),
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
  message.success(t('convert.editor.merged', { count: pendingIds.size }))
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
  if (!pages.length) throw new Error(t('convert.message.noRenderContent'))
  const result = await requireData(publicationRender.batchA4({
    pages,
    source_pages: buildBatchRenderSourcePages(),
    render_page_ocr_texts: currentRenderPageOcrTextsForRequest(),
    target_key: settings.targetKey,
    accidental_mode: settings.accidentalMode,
    measure_number_mode: settings.measureNumberMode,
    initial_measure_number: Math.max(1, Math.trunc(initialMeasureNumber.value || 1)),
    title: t('convert.exportTitle'),
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
        t('convert.message.renderStateSaveFailed', { msg: error instanceof Error ? error.message : String(error) }),
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
    title: t('convert.exportTitle'),
  })
}

function buildBatchRenderSourcePages() {
  return buildBatchRenderRequests(batchRenderSourcePages(), {
    jianpuText: operationalJianpuText.value,
    title: t('convert.exportTitle'),
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
  if (!(await confirmDiscardUnsaved('reset'))) return
  store.setBusy(true)
  try {
    if (editMode.value) {
      editMode.value = false
    }
    deletedEntityIds.value = new Set()
    candidateSelections.value = {}

    const result = await requireData(convertApi.musicxmlToJianpu({
      musicxml_file_id: store.musicxmlFileId,
      target_key: settings.targetKey,
      accidental_mode: settings.accidentalMode,
      polyphony_mode: settings.polyphonyMode,
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
        recognitionCandidateSelections: {},
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
    const resetWarnings = result.warnings ?? []
    for (const warning of resetWarnings) {
      log.addLog(warning, 'warn')
    }
    log.addLog(t('convert.message.resetLog'))
    message.success(t('convert.message.resetDone'))
  } catch (e: unknown) {
    const raw = e instanceof Error ? e.message : String(e)
    const msg = e instanceof ApiError ? handleMissingMusicxml(raw) : raw
    log.addError(t('convert.message.resetFailed', { msg }))
    message.error(msg)
  } finally {
    store.setBusy(false)
  }
}

async function enterEditMode() {
  if (!canLoadMarkerData.value) {
    message.warning(t('convert.marker.missingSourceData'))
    return
  }
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
  // 取消 = 放弃本次所有暂存：删除集合与候选选择都回到已应用基线
  deletedEntityIds.value = new Set(store.currentPage?.deletedSourceIds ?? [])
  candidateSelections.value = { ...(store.currentPage?.recognitionCandidateSelections ?? {}) }
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
    message.warning(sheets.length ? t('convert.marker.multiPageOmr') : t('convert.marker.noSafeMark'))
    return
  }
  correctableSheet.value = sheets[0] ?? null
  candidateSelections.value = { ...(store.currentPage?.recognitionCandidateSelections ?? {}) }
}

/**
 * 选择候选只写入本地暂存：五线谱上用覆盖层即时预览，
 * 简谱与 MusicXML 必须等用户点「应用」才会变。
 */
function selectCandidate(sourceId: string, shape: string): void {
  if (applying.value) return
  const candidate = selectedEntityCandidates.value.find((item) => item.shape === shape)
  const isCurrentEntity = selectedEntity.value?.source_id === sourceId
  const isCurrentGlyph = selectedGlyph.value?.glyph_id === sourceId
  if (!candidate || (!isCurrentEntity && !isCurrentGlyph)) return
  if (candidateSelections.value[sourceId] === shape) return
  candidateSelections.value = { ...candidateSelections.value, [sourceId]: shape }
  // 选中候选意味着这个标记要保留，顺带撤销它待删除的状态。
  if (deletedEntityIds.value.has(sourceId)) {
    const next = new Set(deletedEntityIds.value)
    next.delete(sourceId)
    deletedEntityIds.value = next
  }
}

/** 未识别字形应用后会成为乐谱里的真实音符：点击它定位到简谱对应位置。 */
async function locateGlyphInJianpu(glyphId: string): Promise<void> {
  // 插入音符的来源被解析成 glyph 自身的 id（s1:g7），旧数据则可能是 MusicXML 元素 id（st__n-s1-g7）
  const keys = [glyphId, `st__n-${glyphId.replace(/:/g, '-')}`]
  const anchor = store.textAnchors.find(
    (item) => keys.some((key) => item.source_id === key || item.source_id.startsWith(`${key}__`)),
  )
  if (!anchor) {
    message.info(t('convert.marker.glyphNotApplied'))
    return
  }
  await handleOriginalSourceClick(anchor.source_id)
  // 定位会清空 selectedGlyphId，这里补回来，让符号保持选中框
  selectedGlyphId.value = glyphId
}

/** 左键点未识别字形：编辑态撤销插入，非编辑态定位到简谱。 */
function selectSuspiciousGlyph(glyphId: string, openEditor = true): void {
  selectedGlyphId.value = glyphId
  selectedSourceId.value = ''
  if (!editMode.value) {
    void locateGlyphInJianpu(glyphId)
    return
  }
  if (openEditor) return
  if (!(glyphId in candidateSelections.value)) return
  const next = { ...candidateSelections.value }
  delete next[glyphId]
  candidateSelections.value = next
}

function toggleEntityDelete(sourceId: string) {
  const next = new Set(deletedEntityIds.value)
  if (next.has(sourceId)) {
    next.delete(sourceId)
  } else {
    next.add(sourceId)
    if (sourceId in candidateSelections.value) {
      const selections = { ...candidateSelections.value }
      delete selections[sourceId]
      candidateSelections.value = selections
    }
  }
  deletedEntityIds.value = next
}

/** 「已编辑」= 删除状态或识别形状相对已应用基线发生了变化。 */
const editedCount = computed(() => {
  const baseDeleted = new Set(store.currentPage?.deletedSourceIds ?? [])
  const baseSelections = store.currentPage?.recognitionCandidateSelections ?? {}
  const ids = new Set<string>([
    ...deletedEntityIds.value,
    ...baseDeleted,
    ...Object.keys(effectiveCandidateSelections.value),
    ...Object.keys(baseSelections),
  ])
  let count = 0
  for (const id of ids) {
    const deletedChanged = deletedEntityIds.value.has(id) !== baseDeleted.has(id)
    const selectionChanged = (effectiveCandidateSelections.value[id] ?? '')
      !== (baseSelections[id] ?? '')
    if (deletedChanged || selectionChanged) count += 1
  }
  return count
})

async function applyCorrections(options: {
  keepEditing?: boolean
  silent?: boolean
} = {}): Promise<boolean> {
  const page = store.currentPage
  if (!page) return false
  if (!canEditMarkers.value) {
    message.warning(t('convert.marker.missingMusicxml'))
    return false
  }
  const baseline = new Set(page.deletedSourceIds ?? [])
  const current = deletedEntityIds.value
  const baselineSelections = page.recognitionCandidateSelections ?? {}
  const selectedChanges = Object.keys(effectiveCandidateSelections.value).some(
    (id) => effectiveCandidateSelections.value[id] !== baselineSelections[id],
  ) || Object.keys(baselineSelections).some((id) => !effectiveCandidateSelections.value[id])
  const hasPendingChange = selectedChanges ||
    [...current].some((id) => !baseline.has(id)) ||
    [...baseline].some((id) => !current.has(id))
  if (!hasPendingChange) {
    if (!options.silent) message.info(t('convert.marker.noChanges'))
    return false
  }
  const deletedSourceIds = [...current]
  const candidateSelectionPayload = { ...effectiveCandidateSelections.value }
  const editedPageText = currentPageJianpuText()
  applying.value = true
  try {
    const preserveEditedText = await hasJianpuTextEdits(
      editedPageText,
      page.textAnchorBaselineText,
      page.textHash,
      page.jianpuDirty,
    )
    const data = await requireData(correctApi.apply({
      original_musicxml: page.originalMusicxml,
      deleted_source_ids: deletedSourceIds,
      candidate_selections: candidateSelectionPayload,
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
      message.warning(t('convert.marker.pageSwitched'))
      return false
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
      deletedSourceIds,
      recognitionCandidateSelections: { ...data.applied_candidate_selections },
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
    candidateSelections.value = { ...data.applied_candidate_selections }
    store.setBatchJianpuText(nextBatchText, false)
    store.setBatchRenderPageFileIds([])
    setFinalSvgFileIds([])
    const correctionWarnings = data.warnings ?? []
    for (const warning of correctionWarnings) {
      log.addLog(warning, 'warn')
    }
    if (!options.silent) message.success(t('convert.marker.applied'))
    if (!options.keepEditing) editMode.value = false
    return true
  } catch (e: unknown) {
    const detail = e instanceof Error ? e.message : String(e)
    log.addError(t('convert.marker.applyFailed', { detail }))
    message.error(detail)
    return false
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
  message.success(direction > 0 ? t('convert.editor.octaveUpDone') : t('convert.editor.octaveDownDone'))
}

async function saveJianpu(): Promise<void> {
  if (!canSaveCurrentPage.value) {
    message.warning(t('convert.message.nothingToSave'))
    return
  }
  store.setBusy(true)
  errorLine.value = -1
  try {
    const batchId = store.currentBatchId
    if (!batchId) throw new Error(t('convert.message.noBatch'))
    await workspacePersistence.saveBatch(store, batchId)
    log.addLog(t('convert.message.savedOmr'))
    message.success(t('convert.message.saved'))
  } catch (e: unknown) {
    if (isRenderAborted(e)) return
    const raw = e instanceof Error ? e.message : String(e)
    errorLine.value = extractErrorLineFromMessage(raw)
    log.addError(t('convert.message.saveFailed', { msg: raw }))
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
    if (handleJianpuOutputBlocked('render', e)) return
    errorLine.value = extractErrorLineFromMessage(msg)
    log.addError(t('convert.message.renderFailed', { msg }))
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
  if (source === 'reset') return t('convert.snapshot.sourceReset')
  if (source === 'auto') return t('convert.snapshot.sourceAuto')
  return t('convert.snapshot.sourceSave')
}

async function restoreJianpuSnapshot(snapshot: JianpuSnapshotItem): Promise<void> {
  if (!(await confirmDiscardUnsaved('restore'))) return
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
  log.addLog(t('convert.snapshot.restoredLog', { label, time }))
  message.success(t('convert.snapshot.restored', { label, time }))
}

function confirmDiscardUnsaved(action: 'reset' | 'restore'): Promise<boolean> {
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
async function persistUnsavedBeforeReplace(action: ConvertAction): Promise<boolean> {
  store.setBusy(true)
  try {
    await flushPendingEdits()
    if (!store.hasUnsavedChanges) return true
    const result = await workspacePersistence.saveAllUnsavedBatches(store, {
      mode: 'discard',
    })
    if (result.savedBatchIds.length) {
      log.addLog(t('convert.message.autoSaved', { action: actionLabel(action) }))
    }
    return true
  } catch (e: unknown) {
    if (isRenderAborted(e)) return false
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(t('convert.message.autoSaveFailedLog', { action: actionLabel(action), msg }))
    message.error(t('convert.message.autoSaveFailedMsg', { action: actionLabel(action), msg }))
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

.jianpu-live-layout { height:100%; width:100%; min-height:0; display:grid; gap:0; }
.jianpu-live-editor { min-height:0; overflow:hidden; display:flex; flex-direction:column; }
.jianpu-live-divider {
  cursor: row-resize;
  position: relative;
  background: var(--bg-surface);
}
.jianpu-live-divider::before {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  transform: translateY(-50%);
  background: var(--border);
  transition: background 0.2s;
}
.jianpu-live-divider::after {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 56px;
  height: 5px;
  border-radius: 3px;
  background: var(--border);
  box-shadow: 0 0 0 3px var(--bg-surface);
  transition: background 0.2s, width 0.2s;
}
.jianpu-live-divider:hover::before {
  background: var(--accent);
}
.jianpu-live-divider:hover::after {
  background: var(--accent);
  width: 72px;
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
  gap: 8px;
  min-height: 34px;
  padding: 4px 8px 4px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.panel-head-title {
  flex: 0 0 auto;
  white-space: nowrap;
}

/* 面板标题是大写小标签，按钮文案保持原样，避免英文界面变成全大写 */
.ws-panel-head :deep(.n-button) {
  letter-spacing: 0;
  text-transform: none;
}

.panel-head-label {
  display: inline-flex;
  align-items: center;
  gap: 12px;
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
  border-bottom: 1px solid var(--border-light);
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
  background: var(--border-light);
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
  border-right: 1px solid var(--border-light);
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
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  font-weight: 400;
  color: var(--text-tertiary);
  font-size: 10px;
  letter-spacing: 0;
  text-align: right;
  text-overflow: ellipsis;
  text-transform: none;
  white-space: nowrap;
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
  gap: 8px;
  padding: 6px;
}

.ws-panel-body > .original-preview {
  flex: 1 1 auto;
  min-width: 0;
}

/* 编辑入口与提交按钮放在面板标题行内，保持单行高度 */
.marker-edit-controls {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.edited-count {
  padding: 0 7px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--text-primary) 7%, transparent);
  color: var(--text-secondary);
  font-size: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  line-height: 16px;
  text-transform: none;
  white-space: nowrap;
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

<style>
body.live-resizing {
  user-select: none;
  cursor: row-resize;
}

body.live-resizing .jianpu-live-editor,
body.live-resizing .live-preview {
  pointer-events: none;
}
</style>
