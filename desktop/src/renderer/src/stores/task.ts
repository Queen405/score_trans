import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TaskPageStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TaskPage {
  id: string
  inputFileName: string
  inputFileId: string
  originalFileName: string
  originalFileId: string
  musicxmlFileId: string
  musicxmlText: string
  jianpuText: string
  svgFileId: string
  status: TaskPageStatus
  errorMessage: string
}

function createPage(seed?: Partial<TaskPage>): TaskPage {
  const random = Math.random().toString(36).slice(2, 8)
  return {
    id: `${Date.now().toString(36)}-${random}`,
    inputFileName: '',
    inputFileId: '',
    originalFileName: '',
    originalFileId: '',
    musicxmlFileId: '',
    musicxmlText: '',
    jianpuText: '',
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
  const svgFileId = ref('')
  const isBusy = ref(false)
  const pages = ref<TaskPage[]>([])
  const currentPageIndex = ref(-1)

  function syncCurrentFromPage(): void {
    const page = pages.value[currentPageIndex.value]
    if (!page) {
      inputFileName.value = ''
      inputFileId.value = ''
      originalFileName.value = ''
      originalFileId.value = ''
      musicxmlFileId.value = ''
      musicxmlText.value = ''
      jianpuText.value = ''
      svgFileId.value = ''
      return
    }

    inputFileName.value = page.inputFileName
    inputFileId.value = page.inputFileId
    originalFileName.value = page.originalFileName
    originalFileId.value = page.originalFileId
    musicxmlFileId.value = page.musicxmlFileId
    musicxmlText.value = page.musicxmlText
    jianpuText.value = page.jianpuText
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
    inputFileId.value = fileId
    clearDerived()
    patchCurrentPage({
      inputFileName: name,
      inputFileId: fileId,
      originalFileName: '',
      originalFileId: '',
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: '',
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
    svgFileId.value = ''
    patchCurrentPage({
      musicxmlFileId: '',
      musicxmlText: '',
      jianpuText: '',
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

  function setJianpu(text: string) {
    jianpuText.value = text
    patchCurrentPage({ jianpuText: text })
  }

  function setSvg(fileId: string) {
    svgFileId.value = fileId
    patchCurrentPage({ svgFileId: fileId })
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

  function setCurrentPageStatus(status: TaskPageStatus, errorMessage = '') {
    patchCurrentPage({ status, errorMessage })
  }

  function setBusy(value: boolean) {
    isBusy.value = value
  }

  function reset() {
    inputFileName.value = ''
    inputFileId.value = ''
    originalFileName.value = ''
    originalFileId.value = ''
    musicxmlFileId.value = ''
    musicxmlText.value = ''
    jianpuText.value = ''
    svgFileId.value = ''
    isBusy.value = false
    pages.value = []
    currentPageIndex.value = -1
  }

  return {
    inputFileName,
    inputFileId,
    originalFileName,
    originalFileId,
    musicxmlFileId,
    musicxmlText,
    jianpuText,
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
    setSvg,
    removePage,
    setCurrentPageStatus,
    setBusy,
    reset,
  }
})
