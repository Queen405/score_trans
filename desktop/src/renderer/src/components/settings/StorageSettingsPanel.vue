<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>文件位置</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="用户数据"
        >
          <n-input
            v-model:value="settings.draft.dataDir"
            placeholder="用户数据目录"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectDirectory('data')"
              >
                浏览
              </n-button>
            </template>
          </n-input>
        </settings-form-row>

        <settings-form-row
          label="缓存位置"
        >
          <n-input
            v-model:value="settings.draft.cacheDir"
            placeholder="缓存目录"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectDirectory('cache')"
              >
                浏览
              </n-button>
            </template>
          </n-input>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>缓存管理</h3>
      </div>

      <div class="sv-storage-summary">
        <div>
          <span>当前占用</span>
          <strong>{{ cacheSizeLabel }}</strong>
        </div>
        <n-popconfirm @positive-click="clearCache">
          <template #trigger>
            <n-button
              size="small"
              secondary
              :loading="clearingCache"
            >
              清理缓存
            </n-button>
          </template>
          将删除中间文件和未被历史记录引用的上传副本。
        </n-popconfirm>
      </div>

      <n-alert
        v-if="settings.storageRestartRequired"
        class="sv-inline-alert"
        type="warning"
        size="small"
      >
        <div class="sv-alert-content">
          <span>存储路径已保存，重启应用后生效。</span>
          <n-button
            size="tiny"
            type="warning"
            secondary
            @click="restartApp"
          >
            立即重启
          </n-button>
        </div>
      </n-alert>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  NAlert,
  NButton,
  NInput,
  NPopconfirm,
  useMessage,
} from 'naive-ui'
import { useLogStore } from '../../stores/log'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()
const clearingCache = ref(false)

const cacheSizeLabel = computed(() =>
  settings.cacheSizeAvailable
    ? formatBytes(settings.cacheSizeBytes)
    : '未获取（请重启应用）',
)

async function selectDirectory(target: 'data' | 'cache'): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (!result) return
  if (target === 'data') settings.draft.dataDir = result
  else settings.draft.cacheDir = result
}

async function clearCache(): Promise<void> {
  clearingCache.value = true
  try {
    const result = await settings.clearCache()
    log.addLog(`已清理缓存：${formatBytes(result.freed_bytes)}`)
    message.success(`已清理 ${formatBytes(result.freed_bytes)}`)
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : String(error)
    log.addError(`清理缓存失败：${text}`)
    message.error(text)
  } finally {
    clearingCache.value = false
  }
}

async function restartApp(): Promise<void> {
  await settings.relaunchApp()
}

function desktopApi() {
  return window.api
}

function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`
}
</script>
