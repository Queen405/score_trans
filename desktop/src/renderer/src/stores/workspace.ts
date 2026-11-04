import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { t } from '../i18n'
import type {
  RenderPageOcrText,
  SSEProgressEvent,
  SourceTextAttachment,
  TextAnchor,
} from '../models/types'
import {
  removeJianpuPageSection,
  restoreJianpuPageText,
} from '../utils/jianpuPageSections'
import {
  acknowledgeRevision,
  captureEditedRevision,
  createRevisionState,
  hasUnsavedChangeKind,
  hasUnsavedChanges as revisionHasUnsavedChanges,
  markEdited,
  type BatchRevisionState,
  type ChangeRevision,
  type UserChangeKind,
} from '../utils/unsavedChangeState'

export type TaskPageStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'unrecognized'

export interface TaskPage {
  id: string
  batchId: string
  batchLabel: string
  batchSealed: boolean
  historyPageId: number | null
  historyBatchId: number | null
  taskId: string
  inputFileName: string
  inputFileId: string
  sourceDocumentFileId: string
  sourceDocumentName: string
  sourcePageIndex: number
  originalFileName: string
  originalFileId: string
  musicxmlFileId: string
  musicxmlText: string
  jianpuText: string
  ocrText: string
  jianpuDirty: boolean
  svgFileId: string
  svgFileIds: string[]
  overlayFileId: string
  sourceMapFileId: string
  textAnchors: TextAnchor[]
  textAnchorBaselineText: string
  textAnchorBaselineAnchors: TextAnchor[]
  textAttachments: SourceTextAttachment[]
  textHash: string
  status: TaskPageStatus
  progressPercent: number
  progressMessage: string
  errorMessage: string
  omrFileId: string
  originalMusicxml: string
  workingMusicxml: string
  deletedSourceIds: string[]
  recognitionCandidateSelections: Record<string, string>
}

export interface TaskPageInput {
  inputFileName: string
  batchId?: string
  batchLabel?: string
  batchSealed?: boolean
  historyPageId?: number | null
  historyBatchId?: number | null
  taskId?: string
  inputFileId: string
  sourceDocumentFileId?: string
  sourceDocumentName?: string
  sourcePageIndex?: number
  originalFileName?: string
  originalFileId?: string
  musicxmlFileId?: string
  musicxmlText?: string
  jianpuText?: string
  ocrText?: string
  jianpuDirty?: boolean
  svgFileId?: string
  svgFileIds?: string[]
  overlayFileId?: string
  sourceMapFileId?: string
  textAnchors?: TextAnchor[]
  textAnchorBaselineText?: string
  textAnchorBaselineAnchors?: TextAnchor[]
  textAttachments?: SourceTextAttachment[]
  textHash?: string
  status?: TaskPageStatus
  progressPercent?: number
  progressMessage?: string
  errorMessage?: string
  omrFileId?: string
  originalMusicxml?: string
  workingMusicxml?: string
  deletedSourceIds?: string[]
  recognitionCandidateSelections?: Record<string, string>
}

function createPage(seed?: Partial<TaskPage>): TaskPage {
  const random = Math.random().toString(36).slice(2, 8)
  return {
    id: `${Date.now().toString(36)}-${random}`,
    batchId: '',
    batchLabel: '',
    batchSealed: false,
    historyPageId: null,
    historyBatchId: null,
    taskId: '',
    inputFileName: '',
    inputFileId: '',
    sourceDocumentFileId: '',
    sourceDocumentName: '',
    sourcePageIndex: -1,
    originalFileName: '',
    originalFileId: '',
    musicxmlFileId: '',
    musicxmlText: '',
    jianpuText: '',
    ocrText: '',
    jianpuDirty: false,
    svgFileId: '',
    svgFileIds: [],
    overlayFileId: '',
    sourceMapFileId: '',
    textAnchors: [],
    textAnchorBaselineText: '',
    textAnchorBaselineAnchors: [],
    textAttachments: [],
    textHash: '',
    status: 'pending',
    progressPercent: 0,
    progressMessage: '',
    errorMessage: '',
    omrFileId: '',
    originalMusicxml: '',
    workingMusicxml: '',
    deletedSourceIds: [],
    recognitionCandidateSelections: {},
    ...seed,
  }
}

function cloneTextAttachments(items: SourceTextAttachment[]): SourceTextAttachment[] {
  return items.map((item) => ({
    ...item,
    source_bbox: item.source_bbox ? { ...item.source_bbox } : item.source_bbox,
    anchor: { ...item.anchor },
  }))
}

function cloneTextAnchors(items: TextAnchor[]): TextAnchor[] {
  return items.map((anchor) => ({ ...anchor }))
}

export const useWorkspaceStore = defineStore('workspace', () => {
  // ── State ──
  const inputFileName = ref('')
  const inputFileId = ref('')
  const originalFileName = ref('')
  const originalFileId = ref('')
  const musicxmlFileId = ref('')
  const musicxmlText = ref('')
  const jianpuText = ref('')
  const ocrText = ref('')
  const jianpuDirty = ref(false)
  const svgFileId = ref('')
  const svgFileIds = ref<string[]>([])
  const overlayFileId = ref('')
  const sourceMapFileId = ref('')
  const textAnchors = ref<TextAnchor[]>([])
  const textHash = ref('')
  const omrFileId = ref('')
  const originalMusicxml = ref('')
  const workingMusicxml = ref('')
  const isBusy = ref(false)
  const pages = ref<TaskPage[]>([])
  const currentPageIndex = ref(-1)
  const currentBatchId = ref<string | null>(null)
  const historyPageId = ref<number | null>(null)
  const currentTaskId = ref<string | null>(null)
  const taskStatus = ref<SSEProgressEvent['status']>('pending')
  const backgroundTaskCount = ref(0)
  const batchRenderPageFileIds = ref<Record<string, string[]>>({})
  const batchRenderPageOcrTexts = ref<Record<string, Record<number, string>>>({})
  const batchRenderPageOcrDirty = ref<Record<string, Record<number, boolean>>>({})
  const batchRenderOutputStale = ref<Record<string, boolean>>({})
  const batchRenderLayoutKeys = ref<Record<string, string>>({})
  const batchJianpuTexts = ref<Record<string, string>>({})
  const batchJianpuDirty = ref<Record<string, boolean>>({})
  const batchJianpuPendingPageIds = ref<Record<string, string[]>>({})
  const batchUserChangeRevisions = ref<Record<string, BatchRevisionState>>({})
  const batchUnpersistable = ref<Record<string, boolean>>({})

  function syncCurrentFromPage(): void {
    const page = pages.value[currentPageIndex.value]
    if (!page) {
      inputFileName.value = ''
      historyPageId.value = null
      svgFileIds.value = []
      inputFileId.value = ''
      originalFileName.value = ''
      originalFileId.value = ''
      musicxmlFileId.value = ''
      musicxmlText.value = ''
      jianpuText.value = ''
      ocrText.value = ''
      jianpuDirty.value = false
      svgFileId.value = ''
      overlayFileId.value = ''
      sourceMapFileId.value = ''
      textAnchors.value = []
      textHash.value = ''
      omrFileId.value = ''
      originalMusicxml.value = ''
      workingMusicxml.value = ''
      return
    }

    inputFileName.value = page.inputFileName
    historyPageId.value = page.historyPageId
    inputFileId.value = page.inputFileId
    originalFileName.value = page.originalFileName
    originalFileId.value = page.originalFileId
    musicxmlFileId.value = page.musicxmlFileId
    jianpuText.value = page.jianpuText
    ocrText.value = page.ocrText
    jianpuDirty.value = page.jianpuDirty
    svgFileId.value = page.svgFileId
    svgFileIds.value = page.svgFileIds.length ? page.svgFileIds : (page.svgFileId ? [page.svgFileId] : [])
    overlayFileId.value = page.overlayFileId
    sourceMapFileId.value = page.sourceMapFileId
    textAnchors.value = page.textAnchors.map((anchor) => ({ ...anchor }))
    textHash.value = page.textHash
    omrFileId.value = page.omrFileId
    originalMusicxml.value = page.originalMusicxml
    workingMusicxml.value = page.workingMusicxml
  }

  // ── Batch computeds ──
  const batches = computed(() => {
    const map = new Map<string, { id: string; label: string; sealed: boolean; pages: TaskPage[] }>()
    for (const page of pages.value) {
      if (!page.batchId) continue
      let batch = map.get(page.batchId)
      if (!batch) {
        batch = { id: page.batchId, label: page.batchLabel, sealed: page.batchSealed, pages: [] }
        map.set(page.batchId, batch)
      }
      batch.pages.push(page)
    }
    return [...map.values()]
  })

  const currentBatchPages = computed(() =>
    currentBatchId.value
      ? pages.value.filter((p) => p.batchId === currentBatchId.value)
      : pages.value,
  )

  const currentBatchLabel = computed(() => {
    if (!currentBatchId.value) {
      return inputFileName.value || originalFileName.value || 'score'
    }
    const batch = batches.value.find((b) => b.id === currentBatchId.value)
    return batch?.label || inputFileName.value || originalFileName.value || 'score'
  })

  function toGlobalIndex(batchLocalIndex: number): number {
    const batchPages = currentBatchPages.value
    if (batchLocalIndex < 0 || batchLocalIndex >= batchPages.length) return -1
    return pages.value.indexOf(batchPages[batchLocalIndex])
  }

  function patchCurrentPage(patch: Partial<TaskPage>): void {
    const idx = currentPageIndex.value
    if (idx < 0 || idx >= pages.value.length) return
    pages.value[idx] = { ...pages.value[idx], ...patch }
  }

  function patchPageById(pageId: string, patch: Partial<TaskPage>): boolean {
    const idx = pages.value.findIndex((page) => page.id === pageId)
    if (idx < 0) return false
    pages.value[idx] = { ...pages.value[idx], ...patch }
    if (idx === currentPageIndex.value) {
      syncCurrentFromPage()
    }
    return true
  }

  function patchPageByHistoryPageId(historyId: number | null, patch: Partial<TaskPage>): boolean {
    if (!historyId) return false
    const idx = pages.value.findIndex((page) => page.historyPageId === historyId)
    if (idx < 0) return false
    pages.value[idx] = { ...pages.value[idx], ...patch }
    if (idx === currentPageIndex.value) {
      syncCurrentFromPage()
    }
    return true
  }

  function addInputPage(
    name: string,
    fileId: string,
    source: Partial<Pick<TaskPage, 'sourceDocumentFileId' | 'sourceDocumentName' | 'sourcePageIndex'>> = {},
  ): number {
    // Find current draft batch (unsealed) or create a new batch ID
    let bid = currentBatchId.value
    const currentBatch = bid ? batches.value.find((b) => b.id === bid) : undefined
    if (!bid || !currentBatch || currentBatch.sealed) {
      const random = Math.random().toString(36).slice(2, 8)
      bid = `batch-${Date.now().toString(36)}-${random}`
      currentBatchId.value = bid
    }
    const page = createPage({
      batchId: bid,
      batchLabel: name,
      batchSealed: false,
      inputFileName: name,
      historyPageId: null,
      inputFileId: fileId,
      sourceDocumentFileId: source.sourceDocumentFileId ?? '',
      sourceDocumentName: source.sourceDocumentName ?? '',
      sourcePageIndex: source.sourcePageIndex ?? -1,
      status: 'pending',
    })
    // Update batch label if this is the first page in the batch
    const existingBatchPages = pages.value.filter((p) => p.batchId === bid)
    if (existingBatchPages.length > 0) {
      page.batchLabel = existingBatchPages[0]!.batchLabel
    }
    pages.value.push(page)
    currentPageIndex.value = pages.value.length - 1
    syncCurrentFromPage()
    return currentPageIndex.value
  }

  function selectPage(index: number): void {
    if (index < 0 || index >= pages.value.length) return
    currentPageIndex.value = index
    syncCurrentFromPage()
  }

  function selectPageById(pageId: string): number {
    const idx = pages.value.findIndex((page) => page.id === pageId)
    if (idx < 0) return -1
    selectPage(idx)
    return idx
  }

  function nextPage(): void {
    const localIdx = currentBatchPages.value.indexOf(pages.value[currentPageIndex.value])
    if (localIdx >= 0 && localIdx < currentBatchPages.value.length - 1) {
      selectPage(toGlobalIndex(localIdx + 1))
    }
  }

  function prevPage(): void {
    const localIdx = currentBatchPages.value.indexOf(pages.value[currentPageIndex.value])
    if (localIdx > 0) {
      selectPage(toGlobalIndex(localIdx - 1))
    }
  }

  // ── Computed ──
  const hasMusicxml = computed(() => !!musicxmlFileId.value)
  const hasInput = computed(() => !!inputFileId.value)
  const hasOriginal = computed(() => !!originalFileId.value)
  const pageCount = computed(() => currentBatchPages.value.length)
  const currentPage = computed(() => pages.value[currentPageIndex.value] ?? null)
  const canPrevPage = computed(() => {
    const localIdx = currentBatchPages.value.indexOf(pages.value[currentPageIndex.value])
    return localIdx > 0
  })
  const canNextPage = computed(() => {
    const localIdx = currentBatchPages.value.indexOf(pages.value[currentPageIndex.value])
    return localIdx >= 0 && localIdx < currentBatchPages.value.length - 1
  })
  const activePageTaskCount = computed(() => currentBatchPages.value.filter((page) => page.status === 'processing').length)
  const currentBatchRenderPageFileIds = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return []
    return batchRenderPageFileIds.value[batchId] ?? []
  })
  const currentBatchJianpuText = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return jianpuText.value
    return batchJianpuTexts.value[batchId] ?? ''
  })
  const currentBatchJianpuDirty = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return jianpuDirty.value
    return batchJianpuDirty.value[batchId] ?? false
  })
  const currentBatchJianpuPendingPageIds = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return []
    return batchJianpuPendingPageIds.value[batchId] ?? []
  })
  const currentBatchRenderOutputStale = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return false
    return batchRenderOutputStale.value[batchId] === true
      || Object.values(batchRenderPageOcrDirty.value[batchId] ?? {}).some(Boolean)
  })
  const currentBatchRenderLayoutKey = computed(() => {
    const batchId = currentBatchId.value
    return batchId ? (batchRenderLayoutKeys.value[batchId] ?? '') : ''
  })
  const currentBatchRenderPageOcrDirty = currentBatchRenderOutputStale
  const currentBatchHasUnsavedChanges = computed(() => {
    const batchId = currentBatchId.value
    return batchId ? isBatchUnsaved(batchId) : jianpuDirty.value
  })
  const currentBatchOcrUserEdited = computed(() => {
    const batchId = currentBatchId.value
    return batchId ? isBatchChangeKindUnsaved(batchId, 'ocr') : false
  })
  const currentBatchAttachmentUserEdited = computed(() => {
    const batchId = currentBatchId.value
    return batchId ? isBatchChangeKindUnsaved(batchId, 'attachments') : false
  })
  const hasUnsavedChanges = computed(() => {
    if (!currentBatchId.value && jianpuDirty.value) return true
    // 只统计仍存在于 pages 的 batchId：已被 loadBatch/replacePage 整页替换掉的
    // 旧 batchId 是孤儿脏条目，无法保存也不应阻断关闭。
    const live = new Set(
      pages.value.map((p) => p.batchId).filter((id): id is string => Boolean(id)),
    )
    return Object.entries(batchUserChangeRevisions.value).some(
      ([id, rev]) => live.has(id) && revisionHasUnsavedChanges(rev),
    )
  })
  const hasPersistableUnsavedChanges = computed(() => {
    const live = new Set(
      pages.value.map((p) => p.batchId).filter((id): id is string => Boolean(id)),
    )
    return Object.entries(batchUserChangeRevisions.value).some(
      ([id, rev]) => (
        live.has(id)
        && batchUnpersistable.value[id] !== true
        && revisionHasUnsavedChanges(rev)
      ),
    )
  })

  // ── Actions ──
  function setInputFile(name: string, fileId: string) {
    if (currentPageIndex.value < 0 || currentPageIndex.value >= pages.value.length) {
      addInputPage(name, fileId)
      return
    }

    inputFileName.value = name
    historyPageId.value = null
    inputFileId.value = fileId
    clearDerived()
    patchCurrentPage({
      inputFileName: name,
      historyPageId: null,
      historyBatchId: null,
      inputFileId: fileId,
      sourceDocumentFileId: '',
      sourceDocumentName: '',
      sourcePageIndex: -1,
      originalFileName: '',
      originalFileId: '',
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: '',
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      svgFileIds: [],
      overlayFileId: '',
      sourceMapFileId: '',
      textAnchors: [],
      textAnchorBaselineText: '',
      textAnchorBaselineAnchors: [],
      textAttachments: [],
      status: 'pending',
      taskId: '',
      progressPercent: 0,
      progressMessage: '',
      errorMessage: '',
    })
  }

  function setOriginalFile(name: string, fileId: string) {
    originalFileName.value = name
    originalFileId.value = fileId
    patchCurrentPage({ originalFileName: name, originalFileId: fileId })
  }

  function clearOriginalFile() {
    originalFileName.value = ''
    originalFileId.value = ''
    patchCurrentPage({ originalFileName: '', originalFileId: '' })
  }

  function clearDerived() {
    clearOriginalFile()
    musicxmlFileId.value = ''
    jianpuText.value = ''
    ocrText.value = ''
    jianpuDirty.value = false
    svgFileId.value = ''
    svgFileIds.value = []
    overlayFileId.value = ''
    patchCurrentPage({
      musicxmlFileId: '',
      jianpuText: '',
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      svgFileIds: [],
      overlayFileId: '',
      sourceMapFileId: '',
      textAnchors: [],
      textAnchorBaselineText: '',
      textAnchorBaselineAnchors: [],
      textAttachments: [],
      status: 'pending',
      taskId: '',
      progressPercent: 0,
      progressMessage: '',
      errorMessage: '',
    })
  }

  function setMusicxml(fileId: string, text: string) {
    musicxmlFileId.value = fileId
    musicxmlText.value = text
    patchCurrentPage({ musicxmlFileId: fileId, musicxmlText: text })
  }

  function setJianpu(text: string, dirty = false) {
    jianpuText.value = text
    jianpuDirty.value = dirty
    patchCurrentPage({ jianpuText: text, jianpuDirty: dirty })
  }

  function setOcrText(text: string, dirty = false) {
    ocrText.value = text
    if (dirty) jianpuDirty.value = true
    patchCurrentPage({ ocrText: text, jianpuDirty: dirty ? true : jianpuDirty.value })
  }

  function markJianpuClean() {
    jianpuDirty.value = false
    patchCurrentPage({ jianpuDirty: false })
  }

  function setSvg(fileId: string, fileIds?: string[]) {
    const ids = fileIds ?? (fileId ? [fileId] : [])
    svgFileId.value = fileId
    svgFileIds.value = ids
    patchCurrentPage({ svgFileId: fileId, svgFileIds: ids })
  }

  function setBatchRenderPageFileIds(
    fileIds: string[],
    batchId = currentBatchId.value,
    layoutKey?: string,
  ): void {
    if (!batchId) return
    batchRenderPageFileIds.value = {
      ...batchRenderPageFileIds.value,
      [batchId]: [...fileIds],
    }
    if (!fileIds.length) {
      batchRenderOutputStale.value = {
        ...batchRenderOutputStale.value,
        [batchId]: true,
      }
      batchRenderLayoutKeys.value = omitBatchRecord(
        batchRenderLayoutKeys.value,
        batchId,
      )
    } else if (layoutKey !== undefined) {
      batchRenderLayoutKeys.value = {
        ...batchRenderLayoutKeys.value,
        [batchId]: layoutKey,
      }
    }
  }

  function reindexBatchPageMap<T>(
    entries: Record<number, T>,
    removedPageIndex: number,
  ): Record<number, T> {
    const next: Record<number, T> = {}
    for (const [key, value] of Object.entries(entries)) {
      const pageIndex = Number(key)
      if (!Number.isInteger(pageIndex) || pageIndex < 0 || pageIndex === removedPageIndex) continue
      next[pageIndex > removedPageIndex ? pageIndex - 1 : pageIndex] = value
    }
    return next
  }

  function omitBatchRecord<T>(records: Record<string, T>, batchId: string): Record<string, T> {
    return Object.fromEntries(
      Object.entries(records).filter(([id]) => id !== batchId),
    ) as Record<string, T>
  }

  function removeBatchPageState(
    batchId: string,
    removedPageIndex: number,
    removedPageId: string,
    batchHasPages: boolean,
  ): void {
    if (!batchHasPages) {
      batchRenderPageFileIds.value = omitBatchRecord(batchRenderPageFileIds.value, batchId)
      batchRenderPageOcrTexts.value = omitBatchRecord(batchRenderPageOcrTexts.value, batchId)
      batchRenderPageOcrDirty.value = omitBatchRecord(batchRenderPageOcrDirty.value, batchId)
      batchRenderOutputStale.value = omitBatchRecord(batchRenderOutputStale.value, batchId)
      batchRenderLayoutKeys.value = omitBatchRecord(batchRenderLayoutKeys.value, batchId)
      batchJianpuTexts.value = omitBatchRecord(batchJianpuTexts.value, batchId)
      batchJianpuDirty.value = omitBatchRecord(batchJianpuDirty.value, batchId)
      batchJianpuPendingPageIds.value = omitBatchRecord(batchJianpuPendingPageIds.value, batchId)
      batchUserChangeRevisions.value = omitBatchRecord(batchUserChangeRevisions.value, batchId)
      batchUnpersistable.value = omitBatchRecord(batchUnpersistable.value, batchId)
      return
    }

    const batchText = batchJianpuTexts.value[batchId] ?? ''
    if (batchText) {
      setBatchJianpuText(
        removeJianpuPageSection(batchText, removedPageIndex),
        true,
        batchId,
      )
    }
    const renderPageIds = batchRenderPageFileIds.value[batchId]
    if (renderPageIds) {
      batchRenderPageFileIds.value = {
        ...batchRenderPageFileIds.value,
        [batchId]: renderPageIds.filter((_, index) => index !== removedPageIndex),
      }
    }
    batchRenderPageOcrTexts.value = {
      ...batchRenderPageOcrTexts.value,
      [batchId]: reindexBatchPageMap(
        batchRenderPageOcrTexts.value[batchId] ?? {},
        removedPageIndex,
      ),
    }
    batchRenderPageOcrDirty.value = {
      ...batchRenderPageOcrDirty.value,
      [batchId]: reindexBatchPageMap(
        batchRenderPageOcrDirty.value[batchId] ?? {},
        removedPageIndex,
      ),
    }
    batchJianpuPendingPageIds.value = {
      ...batchJianpuPendingPageIds.value,
      [batchId]: (batchJianpuPendingPageIds.value[batchId] ?? [])
        .filter((pageId) => pageId !== removedPageId),
    }
  }

  function setBatchRenderPageOcrText(
    pageIndex: number,
    text: string,
    dirty = true,
    batchId = currentBatchId.value,
  ): void {
    if (!batchId || pageIndex < 0) return
    batchRenderPageOcrTexts.value = {
      ...batchRenderPageOcrTexts.value,
      [batchId]: {
        ...(batchRenderPageOcrTexts.value[batchId] ?? {}),
        [pageIndex]: text,
      },
    }
    batchRenderPageOcrDirty.value = {
      ...batchRenderPageOcrDirty.value,
      [batchId]: {
        ...(batchRenderPageOcrDirty.value[batchId] ?? {}),
        [pageIndex]: dirty,
      },
    }
    if (dirty) {
      markBatchUserEdited('ocr', batchId)
      batchRenderOutputStale.value = {
        ...batchRenderOutputStale.value,
        [batchId]: true,
      }
    }
  }

  function setBatchRenderPageOcrTexts(
    items: RenderPageOcrText[],
    stale = false,
    batchId = currentBatchId.value,
  ): void {
    if (!batchId) return
    const textMap: Record<number, string> = {}
    const dirtyMap: Record<number, boolean> = {}
    for (const item of items) {
      if (item.page_index < 0) continue
      textMap[item.page_index] = item.ocr_text
      dirtyMap[item.page_index] = stale
    }
    batchRenderPageOcrTexts.value = {
      ...batchRenderPageOcrTexts.value,
      [batchId]: textMap,
    }
    batchRenderPageOcrDirty.value = {
      ...batchRenderPageOcrDirty.value,
      [batchId]: dirtyMap,
    }
    batchRenderOutputStale.value = {
      ...batchRenderOutputStale.value,
      [batchId]: stale,
    }
  }

  function batchRenderPageOcrTextFor(batchId: string, pageIndex: number): string {
    return batchRenderPageOcrTexts.value[batchId]?.[pageIndex] ?? ''
  }

  function currentBatchRenderPageOcrText(pageIndex: number): string {
    const batchId = currentBatchId.value
    if (!batchId) return ''
    return batchRenderPageOcrTextFor(batchId, pageIndex)
  }

  function batchRenderPageOcrTextsFor(batchId: string): RenderPageOcrText[] {
    const entries = batchRenderPageOcrTexts.value[batchId] ?? {}
    return Object.entries(entries)
      .map(([pageIndex, text]) => ({
        page_index: Number(pageIndex),
        ocr_text: text,
      }))
      .filter((item) => Number.isFinite(item.page_index) && item.page_index >= 0)
      .sort((a, b) => a.page_index - b.page_index)
  }

  function currentBatchRenderPageOcrTextEntries(): RenderPageOcrText[] {
    const batchId = currentBatchId.value
    if (!batchId) return []
    return batchRenderPageOcrTextsFor(batchId)
  }

  function isBatchRenderPageOcrDirty(batchId: string): boolean {
    return batchRenderOutputStale.value[batchId] === true
      || Object.values(batchRenderPageOcrDirty.value[batchId] ?? {}).some(Boolean)
  }

  function markBatchRenderPageOcrClean(batchId = currentBatchId.value): void {
    if (!batchId) return
    const entries = batchRenderPageOcrTexts.value[batchId] ?? {}
    const cleanMap = Object.fromEntries(
      Object.keys(entries).map((pageIndex) => [pageIndex, false]),
    ) as Record<number, boolean>
    batchRenderPageOcrDirty.value = {
      ...batchRenderPageOcrDirty.value,
      [batchId]: cleanMap,
    }
    batchRenderOutputStale.value = {
      ...batchRenderOutputStale.value,
      [batchId]: false,
    }
  }

  function setBatchJianpuText(
    text: string,
    dirty = true,
    batchId = currentBatchId.value,
  ): void {
    if (!batchId) {
      setJianpu(text, dirty)
      return
    }
    batchJianpuTexts.value = {
      ...batchJianpuTexts.value,
      [batchId]: text,
    }
    batchJianpuDirty.value = {
      ...batchJianpuDirty.value,
      [batchId]: dirty,
    }
    if (dirty) markBatchUserEdited('jianpu', batchId)
    if (!dirty) {
      batchJianpuPendingPageIds.value = {
        ...batchJianpuPendingPageIds.value,
        [batchId]: [],
      }
    }
  }

  function markBatchJianpuClean(batchId = currentBatchId.value): void {
    if (!batchId) {
      markJianpuClean()
      return
    }
    batchJianpuDirty.value = {
      ...batchJianpuDirty.value,
      [batchId]: false,
    }
    acknowledgeBatchChanges(captureBatchChangeRevision(batchId), ['jianpu'], batchId)
  }

  function batchRevisionStateFor(batchId: string): BatchRevisionState {
    return batchUserChangeRevisions.value[batchId] ?? createRevisionState()
  }

  function markBatchUserEdited(
    kind: UserChangeKind,
    batchId = currentBatchId.value,
  ): void {
    if (!batchId) {
      if (kind === 'jianpu') jianpuDirty.value = true
      return
    }
    batchUserChangeRevisions.value = {
      ...batchUserChangeRevisions.value,
      [batchId]: markEdited(batchRevisionStateFor(batchId), kind),
    }
  }

  function markBatchAttachmentUserEdited(batchId = currentBatchId.value): void {
    markBatchUserEdited('attachments', batchId)
  }

  function markBatchUnpersistable(batchId = currentBatchId.value): void {
    if (!batchId) return
    batchUnpersistable.value = {
      ...batchUnpersistable.value,
      [batchId]: true,
    }
  }

  function markHistoryBatchDeleted(historyBatchId: number): void {
    const localBatchIds = new Set(
      pages.value
        .filter((page) => page.historyBatchId === historyBatchId)
        .map((page) => page.batchId)
        .filter((batchId): batchId is string => Boolean(batchId)),
    )
    for (const batchId of localBatchIds) markBatchUnpersistable(batchId)
  }

  function markAllHistoryBatchesDeleted(): void {
    const localBatchIds = new Set(
      pages.value
        .filter((page) => page.historyBatchId !== null)
        .map((page) => page.batchId)
        .filter((batchId): batchId is string => Boolean(batchId)),
    )
    for (const batchId of localBatchIds) markBatchUnpersistable(batchId)
  }

  function captureBatchChangeRevision(
    batchId = currentBatchId.value,
  ): ChangeRevision {
    return captureEditedRevision(
      batchId ? batchRevisionStateFor(batchId) : createRevisionState(),
    )
  }

  function acknowledgeBatchChanges(
    captured: ChangeRevision,
    kinds?: readonly UserChangeKind[],
    batchId = currentBatchId.value,
  ): void {
    if (!batchId) {
      if (!kinds || kinds.includes('jianpu')) markJianpuClean()
      return
    }
    const next = acknowledgeRevision(batchRevisionStateFor(batchId), captured, kinds)
    batchUserChangeRevisions.value = {
      ...batchUserChangeRevisions.value,
      [batchId]: next,
    }
    if (!hasUnsavedChangeKind(next, 'jianpu')) {
      batchJianpuDirty.value = {
        ...batchJianpuDirty.value,
        [batchId]: false,
      }
      pages.value = pages.value.map((page) =>
        page.batchId === batchId ? { ...page, jianpuDirty: false } : page,
      )
      if (currentBatchId.value === batchId) syncCurrentFromPage()
    }
  }

  function isBatchUnsaved(batchId: string): boolean {
    return revisionHasUnsavedChanges(batchRevisionStateFor(batchId))
  }

  function isBatchChangeKindUnsaved(
    batchId: string,
    kind: UserChangeKind,
  ): boolean {
    return hasUnsavedChangeKind(batchRevisionStateFor(batchId), kind)
  }

  function batchJianpuTextFor(batchId: string): string {
    return batchJianpuTexts.value[batchId] ?? ''
  }

  function isBatchJianpuDirty(batchId: string): boolean {
    return batchJianpuDirty.value[batchId] ?? false
  }

  function batchJianpuPendingPageIdsFor(batchId: string): string[] {
    return batchJianpuPendingPageIds.value[batchId] ?? []
  }

  function markBatchJianpuPagePending(pageId: string, batchId = currentBatchId.value): void {
    if (!batchId || !pageId) return
    const pending = batchJianpuPendingPageIds.value[batchId] ?? []
    if (pending.includes(pageId)) return
    batchJianpuPendingPageIds.value = {
      ...batchJianpuPendingPageIds.value,
      [batchId]: [...pending, pageId],
    }
  }

  function clearBatchJianpuPendingPages(batchId = currentBatchId.value): void {
    if (!batchId) return
    batchJianpuPendingPageIds.value = {
      ...batchJianpuPendingPageIds.value,
      [batchId]: [],
    }
  }

  function setHistoryPageId(id: number | null) {
    historyPageId.value = id
    patchCurrentPage({ historyPageId: id })
  }

  function setPageHistoryPageId(index: number, id: number | null) {
    if (index < 0 || index >= pages.value.length) return
    pages.value[index] = { ...pages.value[index], historyPageId: id }
    if (index === currentPageIndex.value) {
      historyPageId.value = id
    }
  }

  function removePage(index: number): void {
    if (index < 0 || index >= pages.value.length) return
    const removedPage = pages.value[index]!
    const batchLocalIndex = pages.value
      .filter((page) => page.batchId === removedPage.batchId)
      .indexOf(removedPage)
    pages.value.splice(index, 1)
    if (removedPage.batchId) {
      const batchHasPages = pages.value.some((page) => page.batchId === removedPage.batchId)
      removeBatchPageState(
        removedPage.batchId,
        batchLocalIndex,
        removedPage.id,
        batchHasPages,
      )
      if (!batchHasPages && currentBatchId.value === removedPage.batchId) {
        currentBatchId.value = pages.value[0]?.batchId ?? null
      }
    }
    if (pages.value.length === 0) {
      currentPageIndex.value = -1
      currentBatchId.value = null
      syncCurrentFromPage()
    } else if (currentPageIndex.value > index) {
      currentPageIndex.value -= 1
      syncCurrentFromPage()
    } else if (currentPageIndex.value >= pages.value.length) {
      currentPageIndex.value = pages.value.length - 1
      syncCurrentFromPage()
    } else if (currentPageIndex.value === index) {
      syncCurrentFromPage()
    }
  }

  function replacePage(index: number, replacementPages: TaskPageInput[], selectOffset = 0): void {
    if (index < 0 || index >= pages.value.length) return
    const sourcePage = pages.value[index]!
    const nextPages = replacementPages.map((p) => createPage({
      batchId: p.batchId || sourcePage.batchId,
      batchLabel: p.batchLabel || sourcePage.batchLabel,
      batchSealed: p.batchSealed ?? sourcePage.batchSealed,
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
      historyBatchId: p.historyBatchId ?? null,
      taskId: p.taskId ?? '',
      inputFileId: p.inputFileId,
      sourceDocumentFileId: p.sourceDocumentFileId ?? '',
      sourceDocumentName: p.sourceDocumentName ?? '',
      sourcePageIndex: p.sourcePageIndex ?? -1,
      originalFileName: p.originalFileName ?? '',
      originalFileId: p.originalFileId ?? '',
      musicxmlFileId: p.musicxmlFileId ?? '',
      musicxmlText: p.musicxmlText ?? '',
      jianpuText: p.jianpuText ?? '',
      ocrText: p.ocrText ?? '',
      jianpuDirty: p.jianpuDirty ?? false,
      svgFileId: p.svgFileId ?? '',
      svgFileIds: p.svgFileIds ?? (p.svgFileId ? [p.svgFileId] : []),
      overlayFileId: p.overlayFileId ?? '',
      sourceMapFileId: p.sourceMapFileId ?? '',
      textAnchors: cloneTextAnchors(p.textAnchors ?? []),
      textAnchorBaselineText: p.textAnchorBaselineText ?? p.jianpuText ?? '',
      textAnchorBaselineAnchors: cloneTextAnchors(
        p.textAnchorBaselineAnchors ?? p.textAnchors ?? [],
      ),
      textAttachments: cloneTextAttachments(p.textAttachments ?? []),
      textHash: p.textHash ?? '',
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      errorMessage: p.errorMessage ?? '',
      omrFileId: p.omrFileId ?? '',
      originalMusicxml: p.originalMusicxml ?? '',
      workingMusicxml: p.workingMusicxml ?? '',
      deletedSourceIds: [...(p.deletedSourceIds ?? [])],
      recognitionCandidateSelections: { ...(p.recognitionCandidateSelections ?? {}) },
    }))
    pages.value.splice(index, 1, ...nextPages)
    if (!pages.value.length) {
      currentPageIndex.value = -1
      syncCurrentFromPage()
      return
    }
    currentPageIndex.value = Math.max(0, Math.min(index + selectOffset, pages.value.length - 1))
    syncCurrentFromPage()
  }

  function replacePageById(pageId: string, replacementPages: TaskPageInput[], selectOffset = 0): boolean {
    const index = pages.value.findIndex((page) => page.id === pageId)
    if (index < 0) return false
    replacePage(index, replacementPages, selectOffset)
    return true
  }

  function setCurrentPageStatus(status: TaskPageStatus, errorMessage = '') {
    patchCurrentPage({ status, errorMessage })
  }

  function setPageStatus(pageId: string, status: TaskPageStatus, errorMessage = ''): boolean {
    return patchPageById(pageId, { status, errorMessage })
  }

  function setBusy(value: boolean) {
    isBusy.value = value
  }

  function setCurrentTask(taskId: string | null, status: SSEProgressEvent['status'] = 'pending') {
    currentTaskId.value = taskId
    taskStatus.value = status
  }

  function setTaskStatus(status: SSEProgressEvent['status']) {
    taskStatus.value = status
  }

  function beginBackgroundTask(): void {
    backgroundTaskCount.value += 1
  }

  function endBackgroundTask(): void {
    backgroundTaskCount.value = Math.max(0, backgroundTaskCount.value - 1)
  }

  function selectBatch(batchId: string): void {
    currentBatchId.value = batchId
    const firstPageIdx = pages.value.findIndex((p) => p.batchId === batchId)
    if (firstPageIdx >= 0) {
      currentPageIndex.value = firstPageIdx
      syncCurrentFromPage()
    }
  }

  function sealCurrentBatch(): void {
    if (!currentBatchId.value) return
    for (let i = 0; i < pages.value.length; i++) {
      if (pages.value[i].batchId === currentBatchId.value) {
        pages.value[i] = { ...pages.value[i], batchSealed: true }
      }
    }
  }

  function reset() {
    inputFileName.value = ''
    historyPageId.value = null
    inputFileId.value = ''
    originalFileName.value = ''
    originalFileId.value = ''
    musicxmlFileId.value = ''
    musicxmlText.value = ''
    jianpuText.value = ''
    ocrText.value = ''
    jianpuDirty.value = false
    svgFileId.value = ''
    svgFileIds.value = []
    overlayFileId.value = ''
    isBusy.value = false
    pages.value = []
    currentPageIndex.value = -1
    currentBatchId.value = null
    currentTaskId.value = null
    taskStatus.value = 'pending'
    backgroundTaskCount.value = 0
    batchRenderPageFileIds.value = {}
    batchRenderPageOcrTexts.value = {}
    batchRenderPageOcrDirty.value = {}
    batchRenderOutputStale.value = {}
    batchRenderLayoutKeys.value = {}
    batchJianpuTexts.value = {}
    batchJianpuDirty.value = {}
    batchJianpuPendingPageIds.value = {}
    batchUserChangeRevisions.value = {}
    batchUnpersistable.value = {}
  }

  function reorderBatchPages(
    historyBatchId: number,
    orderedHistoryPageIds: number[],
    pageUpdates: { jianpuText: string }[],
    batchJianpuText: string,
  ): void {
    const batchPage = pages.value.find((p) => p.historyBatchId === historyBatchId)
    if (!batchPage) return
    const localBatchId = batchPage.batchId

    const pageMap = new Map<number, TaskPage>()
    for (const page of pages.value) {
      if (page.historyBatchId === historyBatchId && page.historyPageId) {
        pageMap.set(page.historyPageId, page)
      }
    }

    const reordered: TaskPage[] = []
    for (let i = 0; i < orderedHistoryPageIds.length; i++) {
      const histId = orderedHistoryPageIds[i]!
      const page = pageMap.get(histId)
      if (!page) continue
      const update = pageUpdates[i]
      reordered.push({
        ...page,
        jianpuText: update?.jianpuText ?? page.jianpuText,
      })
    }

    const currentPageId = pages.value[currentPageIndex.value]?.id
    const firstBatchIndex = pages.value.findIndex(
      (p) => p.historyBatchId === historyBatchId,
    )
    const otherPages = pages.value.filter((p) => p.historyBatchId !== historyBatchId)
    pages.value = [
      ...otherPages.slice(0, Math.max(0, firstBatchIndex)),
      ...reordered,
      ...otherPages.slice(Math.max(0, firstBatchIndex)),
    ]

    setBatchJianpuText(batchJianpuText, false, localBatchId)
    setBatchRenderPageFileIds([], localBatchId)
    setBatchRenderPageOcrTexts([], false, localBatchId)

    if (currentPageId) {
      const newIdx = pages.value.findIndex((p) => p.id === currentPageId)
      currentPageIndex.value = newIdx >= 0 ? newIdx : currentPageIndex.value
    }
    syncCurrentFromPage()
  }

  function loadBatch(
    batchPages: TaskPageInput[],
    selectIndex: number,
    renderPageFileIds: string[] = [],
    batchJianpuText = '',
    renderPageOcrTexts: RenderPageOcrText[] = [],
    renderOutputStale = false,
    renderLayoutKey = '',
  ) {
    const random = Math.random().toString(36).slice(2, 8)
    const bid = `batch-${Date.now().toString(36)}-${random}`
    const firstLabel = batchPages[0]?.inputFileName ?? t('runtime.history.defaultLabel')
    // loadBatch 整页替换 pages.value，旧 batchId 的页面全部消失。
    // 若不在此清空各 per-batch map，下方 spread（...value, [bid]: ...）会保留
    // 旧 batchId 的脏 revision 条目，形成孤儿 —— 孤儿让 hasUnsavedChanges 永真，
    // 关闭时 saveAllUnsavedBatches 找不到可保存批次却仍判脏，抛 "New edits were
    // made while saving"。整页替换意味着只有 bid 存活，直接重置即可。
    batchRenderPageFileIds.value = {}
    batchRenderPageOcrTexts.value = {}
    batchRenderPageOcrDirty.value = {}
    batchRenderOutputStale.value = {}
    batchRenderLayoutKeys.value = {}
    batchJianpuTexts.value = {}
    batchJianpuDirty.value = {}
    batchJianpuPendingPageIds.value = {}
    batchUserChangeRevisions.value = {}
    batchUnpersistable.value = {}
    pages.value = batchPages.map((p) => createPage({
      batchId: bid,
      batchLabel: p.batchLabel ?? firstLabel,
      batchSealed: true,
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
      historyBatchId: p.historyBatchId ?? null,
      taskId: p.taskId ?? '',
      inputFileId: p.inputFileId,
      sourceDocumentFileId: p.sourceDocumentFileId ?? '',
      sourceDocumentName: p.sourceDocumentName ?? '',
      sourcePageIndex: p.sourcePageIndex ?? -1,
      originalFileName: p.originalFileName ?? '',
      originalFileId: p.originalFileId ?? '',
      musicxmlFileId: p.musicxmlFileId ?? '',
      musicxmlText: p.musicxmlText ?? '',
      jianpuText: p.jianpuText ?? '',
      ocrText: p.ocrText ?? '',
      jianpuDirty: p.jianpuDirty ?? false,
      svgFileId: p.svgFileId ?? '',
      svgFileIds: p.svgFileIds ?? (p.svgFileId ? [p.svgFileId] : []),
      overlayFileId: p.overlayFileId ?? '',
      sourceMapFileId: p.sourceMapFileId ?? '',
      textAnchors: cloneTextAnchors(p.textAnchors ?? []),
      textAnchorBaselineText: p.textAnchorBaselineText ?? p.jianpuText ?? '',
      textAnchorBaselineAnchors: cloneTextAnchors(
        p.textAnchorBaselineAnchors ?? p.textAnchors ?? [],
      ),
      textAttachments: cloneTextAttachments(p.textAttachments ?? []),
      textHash: p.textHash ?? '',
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      errorMessage: p.errorMessage ?? '',
      omrFileId: p.omrFileId ?? '',
      originalMusicxml: p.originalMusicxml ?? '',
      workingMusicxml: p.workingMusicxml ?? '',
      deletedSourceIds: [...(p.deletedSourceIds ?? [])],
      recognitionCandidateSelections: { ...(p.recognitionCandidateSelections ?? {}) },
    }))
    currentBatchId.value = bid
    if (renderPageFileIds.length) {
      batchRenderPageFileIds.value = {
        ...batchRenderPageFileIds.value,
        [bid]: [...renderPageFileIds],
      }
      batchRenderLayoutKeys.value = {
        ...batchRenderLayoutKeys.value,
        [bid]: renderLayoutKey,
      }
    }
    setBatchRenderPageOcrTexts(renderPageOcrTexts, renderOutputStale, bid)
    batchJianpuTexts.value = {
      ...batchJianpuTexts.value,
      [bid]: restoreJianpuPageText(batchJianpuText, batchPages),
    }
    batchJianpuDirty.value = {
      ...batchJianpuDirty.value,
      [bid]: false,
    }
    batchJianpuPendingPageIds.value = {
      ...batchJianpuPendingPageIds.value,
      [bid]: [],
    }
    batchUserChangeRevisions.value = {
      ...batchUserChangeRevisions.value,
      [bid]: createRevisionState(),
    }
    const idx = Math.max(0, Math.min(selectIndex, pages.value.length - 1))
    currentPageIndex.value = idx
    syncCurrentFromPage()
  }

  return {
    inputFileName,
    historyPageId,
    inputFileId,
    originalFileName,
    originalFileId,
    musicxmlFileId,
    musicxmlText,
    jianpuText,
    ocrText,
    jianpuDirty,
    svgFileId,
    svgFileIds,
    overlayFileId,
    sourceMapFileId,
    textAnchors,
    textHash,
    omrFileId,
    originalMusicxml,
    workingMusicxml,
    isBusy,
    pages,
    currentPageIndex,
    currentBatchId,
    batches,
    currentBatchPages,
    currentBatchLabel,
    currentTaskId,
    taskStatus,
    backgroundTaskCount,
    batchRenderPageFileIds,
    batchRenderPageOcrTexts,
    batchRenderPageOcrDirty,
    batchRenderOutputStale,
    batchRenderLayoutKeys,
    batchJianpuTexts,
    batchJianpuDirty,
    batchJianpuPendingPageIds,
    batchUserChangeRevisions,
    batchUnpersistable,
    hasMusicxml,
    hasInput,
    hasOriginal,
    pageCount,
    currentPage,
    canPrevPage,
    canNextPage,
    activePageTaskCount,
    currentBatchRenderPageFileIds,
    currentBatchRenderOutputStale,
    currentBatchRenderLayoutKey,
    currentBatchRenderPageOcrDirty,
    currentBatchHasUnsavedChanges,
    currentBatchOcrUserEdited,
    currentBatchAttachmentUserEdited,
    hasUnsavedChanges,
    hasPersistableUnsavedChanges,
    currentBatchJianpuText,
    currentBatchJianpuDirty,
    currentBatchJianpuPendingPageIds,
    addInputPage,
    selectPage,
    selectPageById,
    nextPage,
    prevPage,
    patchPageById,
    patchPageByHistoryPageId,
    setInputFile,
    setOriginalFile,
    clearOriginalFile,
    clearDerived,
    setMusicxml,
    setJianpu,
    setOcrText,
    markJianpuClean,
    setSvg,
    setBatchRenderPageFileIds,
    setBatchRenderPageOcrText,
    setBatchRenderPageOcrTexts,
    batchRenderPageOcrTextFor,
    currentBatchRenderPageOcrText,
    batchRenderPageOcrTextsFor,
    currentBatchRenderPageOcrTextEntries,
    isBatchRenderPageOcrDirty,
    markBatchRenderPageOcrClean,
    setBatchJianpuText,
    markBatchJianpuClean,
    markBatchUserEdited,
    markBatchAttachmentUserEdited,
    markBatchUnpersistable,
    markHistoryBatchDeleted,
    markAllHistoryBatchesDeleted,
    captureBatchChangeRevision,
    acknowledgeBatchChanges,
    isBatchUnsaved,
    isBatchChangeKindUnsaved,
    batchJianpuTextFor,
    isBatchJianpuDirty,
    batchJianpuPendingPageIdsFor,
    markBatchJianpuPagePending,
    clearBatchJianpuPendingPages,
    setHistoryPageId,
    setPageHistoryPageId,
    removePage,
    replacePage,
    replacePageById,
    setCurrentPageStatus,
    setPageStatus,
    setBusy,
    setCurrentTask,
    setTaskStatus,
    beginBackgroundTask,
    endBackgroundTask,
    selectBatch,
    sealCurrentBatch,
    reset,
    reorderBatchPages,
    loadBatch,
  }
})
