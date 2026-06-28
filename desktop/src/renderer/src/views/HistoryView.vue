<template>
  <div class="history-view">
    <div class="hv-header">
      <div>
        <h2>历史</h2>
        <p class="subtitle">共 {{ entries.length }} 条记录</p>
      </div>
      <div class="hv-actions">
        <n-button size="small" secondary @click="loadHistory()" :loading="loading">刷新</n-button>
        <n-popconfirm @positive-click="handleDeleteAll" :show-icon="false">
          <template #trigger>
            <n-button type="error" size="small" :disabled="!entries.length" secondary>清空全部</n-button>
          </template>
          确定删除所有历史记录？此操作不可恢复。
        </n-popconfirm>
      </div>
    </div>

    <div v-if="!loading && !entries.length" class="empty">
      <n-icon size="40" :depth="3"><TimeOutline /></n-icon>
      <p>暂无历史记录</p>
      <span>上传并识别乐谱后，记录会自动保存</span>
    </div>

    <div v-if="loading" class="loading">
      <n-spin size="medium" />
    </div>

    <div v-if="!loading && entries.length" class="hv-list">
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="hv-card"
        @click="handleRestore(entry)"
      >
        <div class="hv-card-top">
          <div class="hv-card-name">
            <span :class="['status-dot', statusClass(entry.status)]" />
            <span>{{ entry.first_file_name || '未知文件' }}</span>
          </div>
          <div class="hv-card-actions" @click.stop>
            <n-popconfirm @positive-click="handleDelete(entry.id)" :show-icon="false">
              <template #trigger>
                <n-button text type="error" size="small"><n-icon size="14"><TrashOutline /></n-icon></n-button>
              </template>
              确定删除此记录？
            </n-popconfirm>
          </div>
        </div>
        <div class="hv-card-meta">
          <span class="hv-time">{{ formatTime(entry.created_at) }}</span>
          <span :class="['hv-status', entry.status]">{{ statusLabel(entry.status) }}</span>
        </div>
        <div class="hv-card-flags">
          <span class="flag">{{ entry.page_count }} 页</span>
          <span v-if="entry.status === 'waiting'" class="flag">待选择</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { historyApi } from '../api/history'
import { filesApi } from '../api/files'
import { listenHistoryUpdated, listenHistoryPagePatched, type HistoryPagePatchDetail } from '../utils/historyEvents'
import {
  isPreviewableHistoryFile,
  parseWaitingMeasureOptions,
} from '../utils/historyPageState'
import { splitJianpuAndOcr } from '../utils/ocrText'
import { liveRecognitionTaskPatch } from '../utils/liveRecognitionState'
import type { HistoryBatch, HistoryBatchListItem, HistoryPage } from '../models/types'
import type { TaskPage } from '../stores/task'
import {
  TimeOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { NButton, NIcon, NPopconfirm, NSpin, useMessage } from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const message = useMessage()

const entries = ref<HistoryBatchListItem[]>([])
const loading = ref(false)
let stopHistoryUpdatedListener: (() => void) | null = null
let stopHistoryPagePatchedListener: (() => void) | null = null
let restoreCheckSeq = 0
let pagePatchReloadTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  loadHistory()
  stopHistoryUpdatedListener = listenHistoryUpdated(() => loadHistory(false))
  stopHistoryPagePatchedListener = listenHistoryPagePatched(handlePagePatched)
})

onUnmounted(() => {
  stopHistoryUpdatedListener?.()
  stopHistoryUpdatedListener = null
  stopHistoryPagePatchedListener?.()
  stopHistoryPagePatchedListener = null
})

async function loadHistory(showLoading = true): Promise<void> {
  if (showLoading) {
    loading.value = true
  }
  try {
    entries.value = await historyApi.list()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`加载历史失败：${msg}`)
  } finally {
    loading.value = false
  }
}

function handlePagePatched(detail: HistoryPagePatchDetail): void {
  if (!detail.patch.status) return
  if (pagePatchReloadTimer) clearTimeout(pagePatchReloadTimer)
  pagePatchReloadTimer = setTimeout(() => {
    pagePatchReloadTimer = null
    void loadHistory(false)
  }, 500)
}

async function handleDelete(id: number): Promise<void> {
  try {
    await historyApi.deleteOne(id)
    entries.value = entries.value.filter((e) => e.id !== id)
    message.success('已删除')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    message.error(msg)
  }
}

async function handleDeleteAll(): Promise<void> {
  try {
    await historyApi.deleteAll()
    entries.value = []
    message.success('已清空')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    message.error(msg)
  }
}

async function handleRestore(entry: HistoryBatchListItem): Promise<void> {
  if (store.isBusy) {
    message.warning('识别任务进行中，完成后再恢复历史记录。')
    return
  }

  let batch: HistoryBatch
  try {
    batch = await historyApi.get(entry.id)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`加载历史详情失败：${msg}`)
    message.error(msg)
    return
  }

  const pages = batch.pages
  if (!pages.length) return
  store.loadBatch(
    pages.map((page) => {
      const split = splitJianpuAndOcr(page.jianpu_text || '')
      return {
        inputFileName: page.input_file_name,
        inputFileId: page.input_file_id,
        originalFileName: isPreviewableHistoryFile(page.input_file_name) ? page.input_file_name : '',
        originalFileId: isPreviewableHistoryFile(page.input_file_name) ? page.input_file_id : '',
        historyPageId: page.id,
        historyBatchId: batch.id,
        musicxmlFileId: page.musicxml_file_id,
        jianpuText: split.jianpuText,
        ocrText: page.ocr_text || split.ocrText,
        svgFileId: page.svg_file_id,
        svgFileIds: page.svg_file_id ? [page.svg_file_id] : [],
        taskId: page.task_id || '',
        startMeasureNumber: page.start_measure_number ?? null,
        status: page.status as any,
        measureNumberOptions: parseWaitingMeasureOptions(page.error_message),
        errorMessage: page.error_message,
        ...liveRecognitionTaskPatch(page.id, page.status),
      }
    }),
    0,
    batch.render_page_file_ids,
    batch.jianpu_text || '',
    batch.render_page_ocr_texts || [],
  )
  await validateRestoredBatchFiles(pages, batch.render_page_file_ids)
  message.success(`已恢复 ${pages.length} 页`)
}

async function validateRestoredBatchFiles(
  pages: HistoryPage[],
  renderPageFileIds: string[] = [],
): Promise<void> {
  const seq = ++restoreCheckSeq
  const fileIds = pages
    .flatMap((page) => [page.input_file_id, page.musicxml_file_id, page.svg_file_id])
    .concat(renderPageFileIds)
    .filter(Boolean)
  if (!fileIds.length) return
  try {
    const exists = await filesApi.existsMany(fileIds)
    if (seq !== restoreCheckSeq) return
    const warnings: string[] = []
    for (const page of pages) {
      const patch: Partial<TaskPage> = {}
      if (page.input_file_id && !exists[page.input_file_id]) {
        patch.inputFileId = ''
        patch.originalFileId = ''
        patch.originalFileName = ''
        warnings.push(`${page.input_file_name}：原始文件已失效`)
      }
      if (page.musicxml_file_id && !exists[page.musicxml_file_id]) {
        patch.musicxmlFileId = ''
        warnings.push(`${page.input_file_name}：MusicXML 已失效`)
      }
      if (page.svg_file_id && !exists[page.svg_file_id]) {
        patch.svgFileId = ''
        patch.svgFileIds = []
        warnings.push(`${page.input_file_name}：SVG 已失效`)
      }
      if (Object.keys(patch).length) {
        store.patchPageByHistoryPageId(page.id, patch)
      }
    }
    const validRenderIds = renderPageFileIds.filter((fileId) => exists[fileId])
    if (validRenderIds.length !== renderPageFileIds.length) {
      store.setBatchRenderPageFileIds(validRenderIds)
      warnings.push('连续 A4 渲染页部分失效')
    }
    if (warnings.length) {
      log.addLog(`历史恢复部分失效：${warnings.join('，')}`, 'warn')
      message.warning(`${warnings.join('；')}，请重新识别或重新上传。`)
    }
  } catch (e: unknown) {
    if (seq === restoreCheckSeq) {
      log.addLog(`校验历史文件失败：${e instanceof Error ? e.message : String(e)}`, 'warn')
    }
  }
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusLabel(status: string): string {
  if (status === 'completed') return '成功'
  if (status === 'waiting') return '待选择'
  if (status === 'processing' || status === 'pending') return '处理中'
  return '失败'
}

function statusClass(status: string): string {
  if (status === 'completed') return 'ok'
  if (status === 'waiting' || status === 'processing' || status === 'pending') return 'waiting'
  return 'err'
}
</script>

<style scoped>
.history-view {
  max-width: 800px;
}

.hv-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.hv-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 0;
}

.hv-actions {
  display: flex;
  gap: 6px;
}

.empty,
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  gap: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
  text-align: center;
}

.empty p {
  font-size: 15px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.hv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hv-card {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-elevated);
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.hv-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.hv-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.hv-card-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.ok { background: var(--success); }
.status-dot.waiting { background: var(--warning); }
.status-dot.err { background: var(--danger); }

.hv-card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.hv-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.hv-status {
  font-size: 11px;
  font-weight: 500;
}

.hv-status.completed { color: var(--success); }
.hv-status.waiting,
.hv-status.processing,
.hv-status.pending { color: var(--warning); }
.hv-status:not(.completed):not(.waiting):not(.processing):not(.pending) { color: var(--danger); }

.hv-card-flags {
  display: flex;
  gap: 4px;
  margin-bottom: 6px;
}

.flag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--accent-light);
  color: var(--accent);
  font-weight: 500;
}

.hv-preview {
  padding: 6px 8px;
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
  margin-top: 4px;
}

.hv-preview code {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'Cascadia Code', 'Consolas', monospace;
}

.hv-error {
  font-size: 12px;
  color: var(--danger);
  margin-top: 4px;
}
</style>
