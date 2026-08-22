import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { syntaxApi } from '../api/syntax'
import type { SyntaxDiagnostic } from '../models/types'

const VALIDATION_DEBOUNCE_MS = 400

export const useSyntaxDiagnosticsStore = defineStore('syntaxDiagnostics', () => {
  const diagnostics = ref<SyntaxDiagnostic[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const activeId = ref<string | null>(null)
  const selectionVersion = ref(0)
  let sequence = 0
  let timer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null

  const errorCount = computed(() => diagnostics.value.filter((item) => item.severity === 'error').length)

  function clear(): void {
    sequence += 1
    if (timer !== null) clearTimeout(timer)
    timer = null
    controller?.abort()
    controller = null
    diagnostics.value = []
    activeId.value = null
    selectionVersion.value += 1
    error.value = null
    loading.value = false
  }

  async function validate(text: string): Promise<void> {
    const requestSequence = ++sequence
    controller?.abort()
    controller = new AbortController()
    if (!text.trim()) {
      diagnostics.value = []
      activeId.value = null
      error.value = null
      loading.value = false
      return
    }
    loading.value = true
    error.value = null
    const result = await syntaxApi.validate({ jianpu_text: text }, controller.signal)
    if (requestSequence !== sequence) return
    loading.value = false
    if (result.error) {
      if (result.error.code === 'aborted') return
      diagnostics.value = []
      activeId.value = null
      error.value = result.error.message
      return
    }
    diagnostics.value = result.data.diagnostics
    if (!diagnostics.value.some((item) => item.id === activeId.value)) activeId.value = null
  }

  function schedule(text: string): void {
    if (timer !== null) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      void validate(text)
    }, VALIDATION_DEBOUNCE_MS)
  }

  function setActive(id: string | null): void {
    activeId.value = id
    selectionVersion.value += 1
  }

  return {
    diagnostics,
    loading,
    error,
    activeId,
    selectionVersion,
    errorCount,
    clear,
    validate,
    schedule,
    setActive,
  }
})
