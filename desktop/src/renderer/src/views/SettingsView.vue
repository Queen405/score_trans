<template>
  <div class="settings-view">
  <div class="sv-content">
    <div class="sv-header">
      <div class="sv-header-text">
        <h2>设置</h2>
      </div>
      <n-button type="primary" size="medium" @click="save">
        <template #icon><n-icon><SaveOutline /></n-icon></template>
        保存配置
      </n-button>
    </div>

    <div class="sv-grid-layout">
      <div class="sv-col sv-col-left">
        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><NewspaperOutline /></n-icon>
            <span>OCR 设置</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>API Key</label>
              <n-input v-model:value="settings.ocrApiKey" type="password" show-password-on="click" :placeholder="settings.ocrApiKeySet ? '已保存（留空不更新）' : 'API Key'" size="small">
                <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>Provider</label>
              <n-select
                v-model:value="settings.ocrProvider"
                :options="providerSelectOptions(settings.ocrProviderOptions)"
                size="small"
              />
            </div>
          </div>
        </n-card>

        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><EyeOutline /></n-icon>
            <span>AI 视觉转写</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>API Key</label>
              <n-input v-model:value="settings.aiApiKey" type="password" show-password-on="click" :placeholder="settings.aiApiKeySet ? '已保存（留空不更新）' : 'API Key'" size="small">
                <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>Provider</label>
              <n-select
                v-model:value="settings.aiProvider"
                :options="providerSelectOptions(settings.aiProviderOptions)"
                size="small"
              />
            </div>
          </div>
        </n-card>

        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><HardwareChipOutline /></n-icon>
            <span>工作台 AI 助手</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>API Key</label>
              <n-input v-model:value="settings.assistantApiKey" type="password" show-password-on="click" :placeholder="settings.assistantApiKeySet ? '已保存（留空不更新）' : 'API Key'" size="small">
                <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>Provider</label>
              <n-select
                v-model:value="settings.assistantProvider"
                :options="providerSelectOptions(settings.assistantProviderOptions)"
                size="small"
              />
            </div>
          </div>
        </n-card>
      </div>

      <div class="sv-col sv-col-right">
        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><BuildOutline /></n-icon>
            <span>外部工具与存储</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>Audiveris 路径</label>
              <n-input v-model:value="settings.audiverisPath" placeholder="audiveris 或 gradlew.bat 路径" size="small">
                <template #prefix><n-icon size="14"><FolderOutline /></n-icon></template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>JDK / JAVA_HOME</label>
              <n-input v-model:value="settings.javaHome" placeholder="JDK 25 路径" size="small">
                <template #prefix><n-icon size="14"><CodeOutline /></n-icon></template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>用户数据路径</label>
              <n-input v-model:value="settings.dataDir" placeholder="用户数据目录" size="small">
                <template #suffix>
                  <n-button size="tiny" quaternary @click="selectDataDir">浏览</n-button>
                </template>
              </n-input>
            </div>
            <div class="sv-form-item">
              <label>缓存路径</label>
              <n-input v-model:value="settings.cacheDir" placeholder="缓存目录" size="small">
                <template #suffix>
                  <n-button size="tiny" quaternary @click="selectCacheDir">浏览</n-button>
                </template>
              </n-input>
            </div>
            <div class="sv-storage-meta-row">
              <div class="sv-storage-meta">
                <span>缓存占用：{{ cacheSizeLabel }}</span>
              </div>
              <n-popconfirm @positive-click="clearCache">
                <template #trigger>
                  <n-button size="small" secondary :loading="clearingCache">
                    <template #icon><n-icon><TrashOutline /></n-icon></template>
                    清理缓存
                  </n-button>
                </template>
                将删除中间文件和未被历史记录引用的上传副本。
              </n-popconfirm>
            </div>
            <n-alert v-if="settings.storageRestartRequired" type="warning" size="small">
              存储路径变更将在重启后生效。
            </n-alert>
            <div class="sv-actions-row">
              <n-button v-if="settings.storageRestartRequired" type="primary" size="small" @click="restartApp">
                <template #icon><n-icon><RefreshOutline /></n-icon></template>
                重启应用
              </n-button>
            </div>
          </div>
        </n-card>

        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><SwapHorizontalOutline /></n-icon>
            <span>转换设置</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>简谱调</label>
              <n-select
                v-model:value="settings.targetKey"
                :options="keyOptions"
                size="small"
                style="width: 80px"
              />
            </div>
            <div class="sv-form-item">
              <label>默认导出路径</label>
              <n-input v-model:value="settings.outputDir" placeholder="留空则每次手动选择" size="small">
                <template #suffix>
                  <n-button size="tiny" quaternary @click="selectOutputDir">浏览</n-button>
                </template>
              </n-input>
            </div>
          </div>
        </n-card>

        <n-card class="sv-card" :bordered="true" size="small">
          <div class="sv-card-title">
            <n-icon size="16" class="sv-card-icon"><SunnyOutline /></n-icon>
            <span>外观</span>
          </div>
          <div class="sv-form">
            <div class="sv-form-item">
              <label>主题模式</label>
              <n-select
                v-model:value="settings.themeMode"
                :options="themeModeOptions"
                size="small"
                style="width: 140px"
                @update:value="settings.setThemeMode"
              />
            </div>
          </div>
        </n-card>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import {
  BuildOutline,
  NewspaperOutline,
  EyeOutline,
  SaveOutline,
  CodeOutline,
  KeyOutline,
  FolderOutline,
  SwapHorizontalOutline,
  RefreshOutline,
  TrashOutline,
  SunnyOutline,
  HardwareChipOutline,
  OptionsOutline,
} from '@vicons/ionicons5'
import {
  NInput,
  NSelect,
  NButton,
  NIcon,
  NCard,
  NAlert,
  NPopconfirm,
  useMessage,
} from 'naive-ui'
import type { LlmProviderOption } from '../models/types'

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()
const clearingCache = ref(false)
const cacheSizeLabel = computed(() =>
  settings.cacheSizeAvailable ? formatBytes(settings.cacheSizeBytes) : '未获取（请重启应用）',
)

const keyOptions = [
  { label: 'C', value: 'C' },
  { label: 'D', value: 'D' },
  { label: 'E', value: 'E' },
  { label: 'F', value: 'F' },
  { label: 'G', value: 'G' },
  { label: 'A', value: 'A' },
  { label: 'B', value: 'B' },
]

const themeModeOptions = [
  { label: '跟随系统', value: 'system' },
  { label: '浅色模式', value: 'light' },
  { label: '深色模式', value: 'dark' },
]

onMounted(() => settings.load())

watch(() => settings.ocrProvider, () => {
  if (settings.loaded) void refreshProviderDetails('ocr')
})
watch(() => settings.aiProvider, () => {
  if (settings.loaded) void refreshProviderDetails('ai')
})
watch(() => settings.assistantProvider, () => {
  if (settings.loaded) void refreshProviderDetails('assistant')
})

async function refreshProviderDetails(kind: 'ocr' | 'ai' | 'assistant'): Promise<void> {
  try {
    await settings.loadProviderDetails(kind)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`加载 Provider 配置失败：${msg}`)
    message.error(msg)
  }
}

async function save(): Promise<void> {
  try {
    const restartNeeded = await settings.save()
    log.addLog('配置已保存')
    message.success(restartNeeded ? '配置已保存，存储路径将在重启后生效' : '配置已保存')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`保存失败：${msg}`)
    message.error(msg)
  }
}

async function selectOutputDir(): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (result) settings.outputDir = result
}

async function selectDataDir(): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (result) settings.dataDir = result
}

async function selectCacheDir(): Promise<void> {
  const result = await desktopApi().selectDirectory()
  if (result) settings.cacheDir = result
}

async function clearCache(): Promise<void> {
  clearingCache.value = true
  try {
    const result = await settings.clearCache()
    log.addLog(`已清理缓存：${formatBytes(result.freed_bytes)}`)
    message.success(`已清理 ${formatBytes(result.freed_bytes)}`)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`清理缓存失败：${msg}`)
    message.error(msg)
  } finally {
    clearingCache.value = false
  }
}

async function restartApp(): Promise<void> {
  await settings.relaunchApp()
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

function desktopApi(): any {
  return (globalThis as any).api
}

function providerSelectOptions(options: LlmProviderOption[]): { label: string; value: string }[] {
  return options.map((option) => ({
    label: option.label,
    value: option.id,
  }))
}
</script>

<style scoped>
.settings-view {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-height: 100%;
  width: 100%;
  margin: 0 auto;
  padding: 24px;
}

.sv-content {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.sv-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.sv-header-text h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 0;
}

.sv-grid-layout {
  display: grid;
  grid-template-columns: 4fr 6fr;
  gap: 24px;
  align-items: start;
  align-content: start;
}

.sv-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.sv-grid-layout {
  display: grid;
  grid-template-columns: 4fr 6fr;
  gap: 24px;
  align-items: stretch;
  align-content: start;
}

.sv-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
}

.sv-col > .sv-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sv-col > .sv-card :deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.sv-col > .sv-card :deep(.n-card__content) > .sv-form {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.sv-card {
  --n-padding-left: 28px;
  --n-padding-right: 28px;
  --n-padding-top: 24px;
  --n-padding-bottom: 24px;
}

.sv-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.sv-card-icon {
  color: var(--text-primary);
}

.sv-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}

.sv-form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sv-form-item.sv-form-item-inline {
  flex-direction: row;
  align-items: center;
  gap: 12px;
}

.sv-form-item.sv-form-item-inline label {
  min-width: unset;
}

.sv-actions-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.sv-storage-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}

.sv-storage-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-tertiary);
  word-break: break-all;
  min-width: 0;
}

.sv-form-item label {
  font-size: 13px;
  color: var(--text-secondary);
  min-width: 80px;
}

@media (max-width: 720px) {
  .sv-grid-layout {
    grid-template-columns: 1fr;
  }
}
</style>
