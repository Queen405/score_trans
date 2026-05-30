import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { LogEntry } from '../models/types'

export const useLogStore = defineStore('log', () => {
  const entries = ref<LogEntry[]>([])

  function addLog(message: string, level: LogEntry['level'] = 'info'): void {
    entries.value.push({
      timestamp: new Date().toLocaleTimeString(),
      level,
      message,
    })
  }

  function addError(message: string): void {
    addLog(message, 'error')
  }

  function clear(): void {
    entries.value = []
  }

  return { entries, addLog, addError, clear }
})
