import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { LogEntry } from '../models/types'

const MAX_LOG_ENTRIES = 1000

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])
  const errorCount = computed(() => entries.value.filter((e) => e.level === 'error').length)
  let nextLogId = 1

  function addLog(message: string, level: LogEntry['level'] = 'info'): void {
    entries.value.push({
      id: nextLogId,
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
    })
    nextLogId += 1
    const overflow = entries.value.length - MAX_LOG_ENTRIES
    if (overflow > 0) entries.value.splice(0, overflow)
  }

  function addError(message: string): void {
    addLog(message, 'error')
  }

  function clear(): void {
    entries.value = []
  }

  return { entries, errorCount, addLog, addError, clear }
})
