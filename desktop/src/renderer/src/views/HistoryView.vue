<template>
  <div class="history-view">
    <!-- Header -->
    <div class="history-header">
      <div class="header-left">
        <n-h3 prefix="bar" style="margin: 0">
          <n-text type="primary">转换历史</n-text>
        </n-h3>
        <n-text depth="3" style="font-size: 13px">
          共 {{ entries.length }} 条记录
        </n-text>
      </div>
      <n-space>
        <n-button @click="loadHistory" :loading="loading" size="small" secondary>
          刷新
        </n-button>
        <n-popconfirm @positive-click="handleDeleteAll" :show-icon="false">
          <template #trigger>
            <n-button
              type="error"
              size="small"
              :disabled="!entries.length"
              secondary
            >
              清空全部
            </n-button>
          </template>
          确定要删除所有历史记录吗？此操作不可恢复。
        </n-popconfirm>
      </n-space>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && !entries.length" class="empty-state">
      <n-icon size="64" :depth="3">
        <TimeOutline />
      </n-icon>
      <n-text depth="3" style="font-size: 15px; margin-top: 12px">
        暂无历史记录
      </n-text>
      <n-text depth="3" style="font-size: 13px">
        上传并识别乐谱后，记录会自动保存
      </n-text>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <n-spin size="large" />
    </div>

    <!-- History list -->
    <div v-if="!loading && entries.length" class="history-list">
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="history-card"
        @click="handleRestore(entry)"
      >
        <div class="card-header">
          <div class="card-title">
            <n-icon size="18" :color="statusColor(entry.status)">
              <component :is="statusIcon(entry.status)" />
            </n-icon>
            <n-ellipsis style="max-width: 260px; font-weight: 600">
              {{ entry.input_file_name || '未知文件' }}
            </n-ellipsis>
          </div>
          <div class="card-actions" @click.stop>
            <n-popconfirm @positive-click="handleDelete(entry.id)" :show-icon="false">
              <template #trigger>
                <n-button text type="error" size="small">
                  <n-icon size="16"><TrashOutline /></n-icon>
                </n-button>
              </template>
              确定删除此记录？
            </n-popconfirm>
          </div>
        </div>

        <div class="card-body">
          <div class="card-meta">
            <n-text depth="3" style="font-size: 12px">
              {{ formatTime(entry.created_at) }}
            </n-text>
            <n-tag
              :type="statusTagType(entry.status)"
              size="tiny"
              round
              :bordered="false"
            >
              {{ statusLabel(entry.status) }}
            </n-tag>
          </div>

          <div class="card-flags">
            <n-tag v-if="entry.musicxml_file_id" size="tiny" :bordered="false" type="info">
              MusicXML
            </n-tag>
            <n-tag v-if="entry.jianpu_text" size="tiny" :bordered="false" type="success">
              简谱
            </n-tag>
            <n-tag v-if="entry.svg_file_id" size="tiny" :bordered="false" type="warning">
              SVG
            </n-tag>
          </div>

          <div v-if="entry.jianpu_text" class="card-preview">
            <n-ellipsis :line-clamp="2" :tooltip="false">
              <code style="font-size: 12px">{{ entry.jianpu_text }}</code>
            </n-ellipsis>
          </div>

          <n-text v-if="entry.error_message" type="error" style="font-size: 12px">
            {{ entry.error_message }}
          </n-text>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useTaskStore } from '../stores/task'
import { useLogStore } from '../stores/log'
import { historyApi } from '../api/history'
import { getFileURL } from '../api/client'
import type { HistoryEntry } from '../models/types'
import {
  CheckmarkCircleOutline,
  CloseCircleOutline,
  TimeOutline,
  DocumentTextOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import {
  NSpace,
  NButton,
  NTag,
  NText,
  NIcon,
  NEllipsis,
  NPopconfirm,
  NSpin,
  NH3,
  useMessage,
} from 'naive-ui'

const store = useTaskStore()
const log = useLogStore()
const message = useMessage()

const entries = ref<HistoryEntry[]>([])
const loading = ref(false)

onMounted(() => loadHistory())

async function loadHistory(): Promise<void> {
  loading.value = true
  try {
    entries.value = await historyApi.list()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`加载历史失败：${msg}`)
  } finally {
    loading.value = false
  }
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
    message.success('已清空所有历史')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    message.error(msg)
  }
}

async function handleRestore(entry: HistoryEntry): Promise<void> {
  // Restore file references to task store
  if (entry.input_file_id) {
    store.setInputFile(entry.input_file_name, entry.input_file_id)
  }
  if (entry.musicxml_file_id) {
    store.setMusicxml(entry.musicxml_file_id, '')
  }
  if (entry.jianpu_text) {
    store.setJianpu(entry.jianpu_text)
  }
  if (entry.svg_file_id) {
    store.setSvg(entry.svg_file_id)
  }
  if (entry.input_file_id && /\.(pdf|png|jpe?g|tiff?|webp)$/i.test(entry.input_file_name)) {
    store.setOriginalFile(entry.input_file_name, entry.input_file_id)
  }
  message.success('已恢复到工作区')
}

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusIcon(status: string) {
  return status === 'completed' ? CheckmarkCircleOutline : CloseCircleOutline
}

function statusColor(status: string): string {
  return status === 'completed' ? '#18a058' : '#d03050'
}

function statusTagType(status: string): 'success' | 'error' {
  return status === 'completed' ? 'success' : 'error'
}

function statusLabel(status: string): string {
  return status === 'completed' ? '成功' : '失败'
}
</script>

<style scoped>
.history-view {
  padding: 4px 0;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.empty-state,
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.history-card {
  border: 1px solid rgba(129, 161, 193, 0.24);
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.24s ease;
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.75), rgba(236, 239, 244, 0.66));
  box-shadow: 0 24px 52px -46px rgba(46, 52, 64, 0.88);
  backdrop-filter: blur(8px);
}

.history-card:hover {
  border-color: rgba(136, 192, 208, 0.82);
  box-shadow: 0 30px 62px -46px rgba(46, 52, 64, 0.88);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.card-flags {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.card-preview {
  padding: 8px 10px;
  background: rgba(94, 129, 172, 0.08);
  border: 1px solid rgba(94, 129, 172, 0.15);
  border-radius: 9px;
  margin-top: 4px;
}

:global(body.n-theme-dark) .history-card {
  border-color: rgba(129, 161, 193, 0.36);
  background: linear-gradient(150deg, rgba(46, 52, 64, 0.9), rgba(59, 66, 82, 0.82));
  box-shadow: 0 32px 68px -48px rgba(0, 0, 0, 0.95);
}

:global(body.n-theme-dark) .history-card:hover {
  border-color: rgba(136, 192, 208, 0.95);
}

:global(body.n-theme-dark) .card-preview {
  background: rgba(136, 192, 208, 0.12);
  border-color: rgba(136, 192, 208, 0.22);
}
</style>
