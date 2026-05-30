import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTaskStore = defineStore('task', () => {
  // ── State ──
  const inputFileName = ref('')
  const inputFileId = ref('')
  const musicxmlFileId = ref('')
  const musicxmlText = ref('')
  const jianpuText = ref('')
  const svgFileId = ref('')
  const isBusy = ref(false)

  // ── Computed ──
  const hasMusicxml = computed(() => !!musicxmlFileId.value)
  const hasInput = computed(() => !!inputFileId.value)

  // ── Actions ──
  function setInputFile(name: string, fileId: string) {
    inputFileName.value = name
    inputFileId.value = fileId
  }

  function setMusicxml(fileId: string, text: string) {
    musicxmlFileId.value = fileId
    musicxmlText.value = text
  }

  function setJianpu(text: string) {
    jianpuText.value = text
  }

  function setSvg(fileId: string) {
    svgFileId.value = fileId
  }

  function setBusy(value: boolean) {
    isBusy.value = value
  }

  function reset() {
    inputFileName.value = ''
    inputFileId.value = ''
    musicxmlFileId.value = ''
    musicxmlText.value = ''
    jianpuText.value = ''
    svgFileId.value = ''
    isBusy.value = false
  }

  return {
    inputFileName,
    inputFileId,
    musicxmlFileId,
    musicxmlText,
    jianpuText,
    svgFileId,
    isBusy,
    hasMusicxml,
    hasInput,
    setInputFile,
    setMusicxml,
    setJianpu,
    setSvg,
    setBusy,
    reset,
  }
})
