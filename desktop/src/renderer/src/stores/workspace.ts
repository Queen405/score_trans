import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  RenderPageOcrText,
  SSEProgressEvent,
  SourceTextAttachment,
  TextAnchor,
} from '../models/types'
import {
  composeJianpuPageText,
  removeJianpuPageSection,
  restoreJianpuPageText,
} from '../utils/jianpuPageSections'

export type TaskPageStatus =
  | 'pending'
  | 'processing'
  | 'waiting'
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
  textAttachments: SourceTextAttachment[]
  textHash: string
  startMeasureNumber: number | null
  status: TaskPageStatus
  progressPercent: number
  progressMessage: string
  measureNumberOptions: number[]
  errorMessage: string
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
  textAttachments?: SourceTextAttachment[]
  textHash?: string
  startMeasureNumber?: number | null
  status?: TaskPageStatus
  progressPercent?: number
  progressMessage?: string
  measureNumberOptions?: number[]
  errorMessage?: string
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
    textAttachments: [],
    textHash: '',
    startMeasureNumber: null,
    status: 'pending',
    progressPercent: 0,
    progressMessage: '',
    measureNumberOptions: [],
    errorMessage: '',
    ...seed,
  }
}

function mergeJianpuTexts(batchPages: TaskPageInput[]): string {
  return composeJianpuPageText(batchPages)
}

function cloneTextAttachments(items: SourceTextAttachment[]): SourceTextAttachment[] {
  return items.map((item) => ({
    ...item,
    source_bbox: item.source_bbox ? { ...item.source_bbox } : item.source_bbox,
    anchor: { ...item.anchor },
  }))
}

export const useWorkspaceStore = defineStore('workspace', () => {
  // ── State ──
  const inputFileName = ref('')
  const inputFileId = ref('')
  const originalFileName = ref('')
  const originalFileId = ref('')
  const musicxmlFileId = ref('')
  const jianpuText = ref('')
  const ocrText = ref('')
  const jianpuDirty = ref(false)
  const svgFileId = ref('')
  const svgFileIds = ref<string[]>([])
  const overlayFileId = ref('')
  const sourceMapFileId = ref('')
  const textAnchors = ref<TextAnchor[]>([])
  const textHash = ref('')
  const startMeasureNumber = ref<number | null>(null)
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
  const batchJianpuTexts = ref<Record<string, string>>({})
  const batchJianpuDirty = ref<Record<string, boolean>>({})
  const batchJianpuPendingPageIds = ref<Record<string, string[]>>({})

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
      startMeasureNumber.value = null
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
    startMeasureNumber.value = page.startMeasureNumber
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

  function addInputPage(name: string, fileId: string): number {
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
  const currentBatchRenderPageOcrDirty = computed(() => {
    const batchId = currentBatchId.value
    if (!batchId) return false
    return Object.values(batchRenderPageOcrDirty.value[batchId] ?? {}).some(Boolean)
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
      textAttachments: [],
      startMeasureNumber: null,
      status: 'pending',
      taskId: '',
      progressPercent: 0,
      progressMessage: '',
      measureNumberOptions: [],
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
    startMeasureNumber.value = null
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
      textAttachments: [],
      startMeasureNumber: null,
      status: 'pending',
      taskId: '',
      progressPercent: 0,
      progressMessage: '',
      measureNumberOptions: [],
      errorMessage: '',
    })
  }

  function setMusicxml(fileId: string, text: string) {
    musicxmlFileId.value = fileId
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

  function setBatchRenderPageFileIds(fileIds: string[], batchId = currentBatchId.value): void {
    if (!batchId) return
    batchRenderPageFileIds.value = {
      ...batchRenderPageFileIds.value,
      [batchId]: [...fileIds],
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
  }

  function setBatchRenderPageOcrTexts(
    items: RenderPageOcrText[],
    dirty = false,
    batchId = currentBatchId.value,
  ): void {
    if (!batchId) return
    const textMap: Record<number, string> = {}
    const dirtyMap: Record<number, boolean> = {}
    for (const item of items) {
      if (item.page_index < 0) continue
      textMap[item.page_index] = item.ocr_text
      dirtyMap[item.page_index] = dirty
    }
    batchRenderPageOcrTexts.value = {
      ...batchRenderPageOcrTexts.value,
      [batchId]: textMap,
    }
    batchRenderPageOcrDirty.value = {
      ...batchRenderPageOcrDirty.value,
      [batchId]: dirtyMap,
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
    return Object.values(batchRenderPageOcrDirty.value[batchId] ?? {}).some(Boolean)
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

  function setPageStartMeasureNumber(value: number | null) {
    startMeasureNumber.value = value
    patchCurrentPage({ startMeasureNumber: value })
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
      const batchText = batchJianpuTexts.value[removedPage.batchId] ?? ''
      if (batchText) {
        setBatchJianpuText(
          removeJianpuPageSection(batchText, batchLocalIndex),
          true,
          removedPage.batchId,
        )
      }
      setBatchRenderPageFileIds([], removedPage.batchId)
      batchJianpuPendingPageIds.value = {
        ...batchJianpuPendingPageIds.value,
        [removedPage.batchId]: (batchJianpuPendingPageIds.value[removedPage.batchId] ?? [])
          .filter((pageId) => pageId !== removedPage.id),
      }
    }
    if (pages.value.length === 0) {
      currentPageIndex.value = -1
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
      textAnchors: (p.textAnchors ?? []).map((anchor) => ({ ...anchor })),
      textAttachments: cloneTextAttachments(p.textAttachments ?? []),
      textHash: p.textHash ?? '',
      startMeasureNumber: p.startMeasureNumber ?? null,
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      measureNumberOptions: p.measureNumberOptions ?? [],
      errorMessage: p.errorMessage ?? '',
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
    jianpuText.value = ''
    ocrText.value = ''
    jianpuDirty.value = false
    svgFileId.value = ''
    svgFileIds.value = []
    overlayFileId.value = ''
    startMeasureNumber.value = null
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
    batchJianpuTexts.value = {}
    batchJianpuDirty.value = {}
    batchJianpuPendingPageIds.value = {}
  }

  function reorderBatchPages(
    historyBatchId: number,
    orderedHistoryPageIds: number[],
    pageUpdates: { jianpuText: string; startMeasureNumber: number | null }[],
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
        startMeasureNumber: update?.startMeasureNumber ?? page.startMeasureNumber,
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
  ) {
    const random = Math.random().toString(36).slice(2, 8)
    const bid = `batch-${Date.now().toString(36)}-${random}`
    const firstLabel = batchPages[0]?.inputFileName ?? '历史记录'
    pages.value = batchPages.map((p) => createPage({
      batchId: bid,
      batchLabel: p.batchLabel ?? firstLabel,
      batchSealed: true,
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
      historyBatchId: p.historyBatchId ?? null,
      taskId: p.taskId ?? '',
      inputFileId: p.inputFileId,
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
      textAnchors: (p.textAnchors ?? []).map((anchor) => ({ ...anchor })),
      textAttachments: cloneTextAttachments(p.textAttachments ?? []),
      textHash: p.textHash ?? '',
      startMeasureNumber: p.startMeasureNumber ?? null,
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      measureNumberOptions: p.measureNumberOptions ?? [],
      errorMessage: p.errorMessage ?? '',
    }))
    currentBatchId.value = bid
    if (renderPageFileIds.length) {
      batchRenderPageFileIds.value = {
        ...batchRenderPageFileIds.value,
        [bid]: [...renderPageFileIds],
      }
    }
    setBatchRenderPageOcrTexts(renderPageOcrTexts, false, bid)
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
    jianpuText,
    ocrText,
    jianpuDirty,
    svgFileId,
    svgFileIds,
    overlayFileId,
    sourceMapFileId,
    textAnchors,
    textHash,
    startMeasureNumber,
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
    hasMusicxml,
    hasInput,
    hasOriginal,
    pageCount,
    currentPage,
    canPrevPage,
    canNextPage,
    activePageTaskCount,
    currentBatchRenderPageFileIds,
    currentBatchRenderPageOcrDirty,
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
    batchJianpuTextFor,
    isBatchJianpuDirty,
    batchJianpuPendingPageIdsFor,
    markBatchJianpuPagePending,
    clearBatchJianpuPendingPages,
    setPageStartMeasureNumber,
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

export const useTaskStore = useWorkspaceStore
