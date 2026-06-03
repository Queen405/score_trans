import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TaskPageStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TaskPage {
  id: string
  historyPageId: number | null
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
  status: TaskPageStatus
  errorMessage: string
}

export interface TaskPageInput {
  inputFileName: string
  historyPageId?: number | null
  inputFileId: string
  originalFileName?: string
  originalFileId?: string
  musicxmlFileId?: string
  musicxmlText?: string
  jianpuText?: string
  ocrText?: string
  jianpuDirty?: boolean
  svgFileId?: string
  status?: TaskPageStatus
  errorMessage?: string
}

function createPage(seed?: Partial<TaskPage>): TaskPage {
  const random = Math.random().toString(36).slice(2, 8)
  return {
    id: `${Date.now().toString(36)}-${random}`,
    historyPageId: null,
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
    status: 'pending',
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
  const musicxmlText = ref('')
  const jianpuText = ref('')
  const ocrText = ref('')
  const jianpuDirty = ref(false)
  const svgFileId = ref('')
  const isBusy = ref(false)
  const pages = ref<TaskPage[]>([])
  const currentPageIndex = ref(-1)
  const historyPageId = ref<number | null>(null)

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
      return
    }

    inputFileName.value = page.inputFileName
    historyPageId.value = page.historyPageId
    inputFileId.value = page.inputFileId
    originalFileName.value = page.originalFileName
    originalFileId.value = page.originalFileId
    musicxmlFileId.value = page.musicxmlFileId
    musicxmlText.value = page.musicxmlText
    jianpuText.value = page.jianpuText
    ocrText.value = page.ocrText
    jianpuDirty.value = page.jianpuDirty
    svgFileId.value = page.svgFileId
  }

  function patchCurrentPage(patch: Partial<TaskPage>): void {
    const idx = currentPageIndex.value
    if (idx < 0 || idx >= pages.value.length) return
    pages.value[idx] = { ...pages.value[idx], ...patch }
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
      status: 'pending',
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
    musicxmlText.value = ''
    jianpuText.value = ''
    ocrText.value = ''
    jianpuDirty.value = false
    svgFileId.value = ''
    patchCurrentPage({
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: '',
      ocrText: '',
      jianpuDirty: false,
      svgFileId: '',
      status: 'pending',
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

  function setSvg(fileId: string) {
    svgFileId.value = fileId
    patchCurrentPage({ svgFileId: fileId })
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
      inputFileId: p.inputFileId,
      originalFileName: p.originalFileName ?? '',
      originalFileId: p.originalFileId ?? '',
      musicxmlFileId: p.musicxmlFileId ?? '',
      musicxmlText: p.musicxmlText ?? '',
      jianpuText: p.jianpuText ?? '',
      ocrText: p.ocrText ?? '',
      jianpuDirty: p.jianpuDirty ?? false,
      svgFileId: p.svgFileId ?? '',
      status: (p.status ?? 'completed') as TaskPageStatus,
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

  function setCurrentPageStatus(status: TaskPageStatus, errorMessage = '') {
    patchCurrentPage({ status, errorMessage })
  }

  function setBusy(value: boolean) {
    isBusy.value = value
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
    isBusy.value = false
    pages.value = []
    currentPageIndex.value = -1
  }

  function loadBatch(batchPages: TaskPageInput[], selectIndex: number) {
    pages.value = batchPages.map((p) => createPage({
      inputFileName: p.inputFileName,
      historyPageId: p.historyPageId ?? null,
      inputFileId: p.inputFileId,
      originalFileName: p.originalFileName ?? '',
      originalFileId: p.originalFileId ?? '',
      musicxmlFileId: p.musicxmlFileId ?? '',
      musicxmlText: p.musicxmlText ?? '',
      jianpuText: p.jianpuText ?? '',
      ocrText: p.ocrText ?? '',
      jianpuDirty: p.jianpuDirty ?? false,
      svgFileId: p.svgFileId ?? '',
      status: (p.status ?? 'completed') as TaskPageStatus,
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
    musicxmlText,
    jianpuText,
    ocrText,
    jianpuDirty,
    svgFileId,
    isBusy,
    pages,
    currentPageIndex,
    hasMusicxml,
    hasInput,
    hasOriginal,
    pageCount,
    currentPage,
    canPrevPage,
    canNextPage,
    addInputPage,
    selectPage,
    nextPage,
    prevPage,
    setInputFile,
    setOriginalFile,
    clearOriginalFile,
    clearDerived,
    setMusicxml,
    setJianpu,
    setOcrText,
    markJianpuClean,
    setSvg,
    setHistoryPageId,
    setPageHistoryPageId,
    removePage,
    replacePage,
    setCurrentPageStatus,
    setBusy,
    reset,
    loadBatch,
  }
})
