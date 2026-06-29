<template>
  <div class="history-quick">
    <n-spin
      v-if="loading"
      size="small"
      class="hq-loading"
    />
    <div
      v-else-if="!entries.length"
      class="hq-empty"
    >
      <n-icon
        size="32"
        :depth="3"
      >
        <TimeOutline />
      </n-icon>
      <span class="hq-empty-text">暂无历史记录</span>
      <span class="hq-empty-hint">识别乐谱后会自动保存到此处</span>
    </div>
    <div
      v-else
      class="hq-list"
    >
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="hq-item"
        :class="{ restoring: restoringId === entry.id }"
        @click="onClick(entry)"
      >
        <span :class="['hq-dot', statusClass(entry.status)]" />
        <div class="hq-info">
          <span class="hq-name">{{ entry.first_file_name || '未知文件' }}</span>
          <span class="hq-meta">
            <span>{{ formatRelative(entry.created_at) }}</span>
            <span
              v-if="entry.page_count > 1"
              class="hq-pages"
            >{{ entry.page_count }} 页</span>
          </span>
        </div>
        <n-icon
          size="14"
          class="hq-arrow"
        >
          <ChevronForwardOutline />
        </n-icon>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { NIcon, NSpin } from 'naive-ui'
import { TimeOutline, ChevronForwardOutline } from '@vicons/ionicons5'
import { historyApi } from '../api/history'
import { listenHistoryUpdated } from '../utils/historyEvents'
import { useHistoryRestore } from '../composables/useHistoryRestore'
import type { HistoryBatchListItem } from '../models/types'

const RECENT_LIMIT = 6

const entries = ref<HistoryBatchListItem[]>([])
const loading = ref(false)
const restoringId = ref<number | null>(null)
let stopListener: (() => void) | null = null

const { restoreBatch } = useHistoryRestore()

onMounted(() => {
  void load()
  stopListener = listenHistoryUpdated(() => void load(false))
})

onUnmounted(() => {
  stopListener?.()
  stopListener = null
})

async function load(showLoading = true): Promise<void> {
  if (showLoading) loading.value = true
  const { data, error } = await historyApi.list()
  if (error) {
    loading.value = false
    return
  }
  entries.value = (data ?? []).slice(0, RECENT_LIMIT)
  loading.value = false
}

function statusClass(status: string): string {
  if (status === 'completed') return 'ok'
  if (status === 'waiting' || status === 'processing' || status === 'pending') return 'waiting'
  return 'err'
}

function formatRelative(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return iso
  const diffMs = Date.now() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = Math.floor(diffHour / 24)
  if (diffDay < 7) return `${diffDay} 天前`
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function onClick(entry: HistoryBatchListItem): Promise<void> {
  if (restoringId.value !== null) return
  restoringId.value = entry.id
  try {
    await restoreBatch(entry)
  } finally {
    restoringId.value = null
  }
}
</script>

<style scoped>
.history-quick {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.hq-loading {
  align-self: center;
  margin-top: 24px;
}

.hq-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 1;
  color: var(--text-tertiary);
}

.hq-empty-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.hq-empty-hint {
  font-size: 11px;
}

.hq-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hq-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}

.hq-item:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.hq-item.restoring {
  opacity: 0.6;
  pointer-events: none;
}

.hq-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.hq-dot.ok { background: var(--success); }
.hq-dot.waiting { background: var(--warning); }
.hq-dot.err { background: var(--danger); }

.hq-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.hq-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hq-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.hq-pages {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--accent-light);
  color: var(--accent);
  font-weight: 500;
}

.hq-arrow {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
</style>
