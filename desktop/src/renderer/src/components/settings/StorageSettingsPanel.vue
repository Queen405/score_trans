<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.storage.location') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.storage.userData')"
        >
          <n-input
            v-model:value="settings.draft.dataDir"
            :placeholder="t('settings.storage.userDataPlaceholder')"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectDirectory('data')"
              >
                {{ t('common.action.browse') }}
              </n-button>
            </template>
          </n-input>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.storage.cache')"
        >
          <n-input
            v-model:value="settings.draft.cacheDir"
            :placeholder="t('settings.storage.cachePlaceholder')"
            size="small"
          >
            <template #suffix>
              <n-button
                size="tiny"
                quaternary
                @click="selectDirectory('cache')"
              >
                {{ t('common.action.browse') }}
              </n-button>
            </template>
          </n-input>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.storage.management') }}</h3>
      </div>

      <div class="sv-storage-summary">
        <div>
          <span>{{ t('settings.storage.currentUsage') }}</span>
          <strong>{{ cacheSizeLabel }}</strong>
        </div>
        <n-popconfirm @positive-click="clearCache">
          <template #trigger>
            <n-button
              size="small"
              secondary
              :loading="clearingCache"
            >
              {{ t('settings.storage.clear') }}
            </n-button>
          </template>
          {{ t('settings.storage.clearConfirm') }}
        </n-popconfirm>
      </div>

      <n-alert
        v-if="settings.storageRestartRequired"
        class="sv-inline-alert"
        type="warning"
        size="small"
      >
        <div class="sv-alert-content">
          <span>{{ t('settings.storage.restartNotice') }}</span>
          <n-button
            size="tiny"
            type="warning"
            secondary
            @click="restartApp"
          >
            {{ t('settings.view.restartNow') }}
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
import { t } from '../../i18n'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()
const clearingCache = ref(false)

const cacheSizeLabel = computed(() =>
  settings.cacheSizeAvailable
    ? formatBytes(settings.cacheSizeBytes)
    : t('settings.storage.usageUnknown'),
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
    log.addLog(t('settings.storage.clearedLog', { size: formatBytes(result.freed_bytes) }))
    message.success(t('settings.storage.cleared', { size: formatBytes(result.freed_bytes) }))
  } catch (error: unknown) {
    const text = error instanceof Error ? error.message : String(error)
    log.addError(t('settings.storage.clearFailed', { text }))
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
