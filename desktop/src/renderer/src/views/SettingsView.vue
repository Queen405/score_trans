<template>
  <div class="settings-view">
    <div class="sv-header">
      <div class="sv-header-text">
        <h2>设置</h2>
        <p class="subtitle">调整识别引擎、导出路径、OCR 与 AI 服务参数</p>
      </div>
      <n-button type="primary" size="medium" @click="save">
        <template #icon><n-icon><SaveOutline /></n-icon></template>
        保存配置
      </n-button>
    </div>

        <div class="sv-grid-layout">
      <n-card class="sv-card" :bordered="true" size="small">
        <div class="sv-card-title">
          <n-icon size="16" class="sv-card-icon"><BuildOutline /></n-icon>
          <span>外部工具</span>
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
        </div>
      </n-card>

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
          <n-icon size="16" class="sv-card-icon"><OptionsOutline /></n-icon>
          <span>识别预处理</span>
        </div>
        <div class="sv-form">
          <div class="sv-form-item sv-form-item-inline">
            <label>启用</label>
            <n-switch v-model:value="settings.omrPreprocess" size="small" />
          </div>
          <div class="sv-form-item">
            <label>目标长边</label>
            <n-input-number v-model:value="settings.omrPreprocessLongEdge" :min="0" :step="200" size="small" style="width: 140px" />
          </div>
          <div class="sv-form-item sv-form-item-inline">
            <label>黑白化</label>
            <n-switch v-model:value="settings.omrPreprocessBinarize" size="small" />
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
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
  OptionsOutline,
} from '@vicons/ionicons5'
import {
  NInput,
  NInputNumber,
  NSelect,
  NSwitch,
  NButton,
  NIcon,
  NCard,
  useMessage,
} from 'naive-ui'
import type { LlmProviderOption } from '../models/types'

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const keyOptions = [
  { label: 'C', value: 'C' },
  { label: 'D', value: 'D' },
  { label: 'E', value: 'E' },
  { label: 'F', value: 'F' },
  { label: 'G', value: 'G' },
  { label: 'A', value: 'A' },
  { label: 'B', value: 'B' },
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
    await settings.save()
    log.addLog('配置已保存')
    message.success('配置已保存')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`保存失败：${msg}`)
    message.error(msg)
  }
}

async function selectOutputDir(): Promise<void> {
  const result = await (window as any).api.selectDirectory()
  if (result) settings.outputDir = result
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
  width: 100%;
  margin: 0 auto;
  padding: 0 24px;
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
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  align-items: start;
}

.sv-grid-layout > .sv-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.sv-grid-layout > .sv-card :deep(.n-card__content) {
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
  color: var(--accent);
  margin-bottom: 20px;
}

.sv-card-icon {
  color: var(--accent);
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
