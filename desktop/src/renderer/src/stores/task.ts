import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SSEProgressEvent } from '../models/types'

export type TaskPageStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TaskPage {
  id: string
  historyPageId: number | null
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
  startMeasureNumber: number | null
  status: TaskPageStatus
  progressPercent: number
  progressMessage: string
  errorMessage: string
}

export interface TaskPageInput {
  inputFileName: string
  historyPageId?: number | null
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
  startMeasureNumber?: number | null
  status?: TaskPageStatus
  progressPercent?: number
  progressMessage?: string
  errorMessage?: string
}

function createPage(seed?: Partial<TaskPage>): TaskPage {
  const random = Math.random().toString(36).slice(2, 8)
  return {
    id: `${Date.now().toString(36)}-${random}`,
    historyPageId: null,
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
    startMeasureNumber: null,
    status: 'pending',
    progressPercent: 0,
    progressMessage: '',
    errorMessage: '',
    ...seed,
  }
}

export const useTaskStore = defineStore('task', () => {
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
  const startMeasureNumber = ref<number | null>(null)
  const isBusy = ref(false)
  const pages = ref<TaskPage[]>([])
  const currentPageIndex = ref(-1)
  const historyPageId = ref<number | null>(null)
  const currentTaskId = ref<string | null>(null)
  const taskStatus = ref<SSEProgressEvent['status']>('pending')
  const backgroundTaskCount = ref(0)

  function syncCurrentFromPage(): void {
    const page = pages.value[currentPageIndex.value]
    if (!page) {
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
    startMeasureNumber.value = page.startMeasureNumber
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

  function addInputPage(name: string, fileId: string): number {
    const page = createPage({
      inputFileName: name,
      historyPageId: null,
      inputFileId: fileId,
      status: 'pending',
    })
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
    selectPage(currentPageIndex.value + 1)
  }

  function prevPage(): void {
    selectPage(currentPageIndex.value - 1)
  }

  // ── Computed ──
  const hasMusicxml = computed(() => !!musicxmlFileId.value)
  const hasInput = computed(() => !!inputFileId.value)
  const hasOriginal = computed(() => !!originalFileId.value)
  const pageCount = computed(() => pages.value.length)
  const currentPage = computed(() => pages.value[currentPageIndex.value] ?? null)
  const canPrevPage = computed(() => currentPageIndex.value > 0)
  const canNextPage = computed(() => currentPageIndex.value >= 0 && currentPageIndex.value < pages.value.length - 1)
  const activePageTaskCount = computed(() => pages.value.filter((page) => page.status === 'processing').length)

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
      inputFileId: fileId,
      originalFileName: '',
      originalFileId: '',
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: '',
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      startMeasureNumber: null,
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
    startMeasureNumber.value = null
    patchCurrentPage({
      musicxmlFileId: '',
      jianpuText: '',
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      startMeasureNumber: null,
      status: 'pending',
      taskId: '',
      progressPercent: 0,
      progressMessage: '',
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

  function setSvg(fileId: string) {
    svgFileId.value = fileId
    patchCurrentPage({ svgFileId: fileId })
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
    pages.value.splice(index, 1)
    if (pages.value.length === 0) {
      currentPageIndex.value = -1
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
    const nextPages = replacementPages.map((p) => createPage({
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
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
      startMeasureNumber: p.startMeasureNumber ?? null,
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
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

  function replacePageByIdKeepingSelection(pageId: string, replacementPages: TaskPageInput[]): TaskPage[] {
    const index = pages.value.findIndex((page) => page.id === pageId)
    if (index < 0) return []
    const selectedPageId = currentPage.value?.id ?? ''
    const nextPages = replacementPages.map((p) => createPage({
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
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
      startMeasureNumber: p.startMeasureNumber ?? null,
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      errorMessage: p.errorMessage ?? '',
    }))
    pages.value.splice(index, 1, ...nextPages)
    const selectedIndex = pages.value.findIndex((page) => page.id === selectedPageId)
    currentPageIndex.value = selectedIndex >= 0
      ? selectedIndex
      : Math.max(0, Math.min(index, pages.value.length - 1))
    syncCurrentFromPage()
    return nextPages
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
    startMeasureNumber.value = null
    isBusy.value = false
    pages.value = []
    currentPageIndex.value = -1
    currentTaskId.value = null
    taskStatus.value = 'pending'
    backgroundTaskCount.value = 0
  }

  function loadBatch(batchPages: TaskPageInput[], selectIndex: number) {
    pages.value = batchPages.map((p) => createPage({
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
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
      startMeasureNumber: p.startMeasureNumber ?? null,
      status: (p.status ?? 'completed') as TaskPageStatus,
      progressPercent: p.progressPercent ?? 0,
      progressMessage: p.progressMessage ?? '',
      errorMessage: p.errorMessage ?? '',
    }))
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
    startMeasureNumber,
    isBusy,
    pages,
    currentPageIndex,
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
    addInputPage,
    selectPage,
    selectPageById,
    nextPage,
    prevPage,
    patchPageById,
    setInputFile,
    setOriginalFile,
    clearOriginalFile,
    clearDerived,
    setMusicxml,
    setJianpu,
    setOcrText,
    markJianpuClean,
    setSvg,
    setPageStartMeasureNumber,
    setHistoryPageId,
    setPageHistoryPageId,
    removePage,
    replacePage,
    replacePageById,
    replacePageByIdKeepingSelection,
    setCurrentPageStatus,
    setPageStatus,
    setBusy,
    setCurrentTask,
    setTaskStatus,
    beginBackgroundTask,
    endBackgroundTask,
    reset,
    loadBatch,
  }
})
