<template>
  <div class="sv-panel">
    <section
      v-for="(service, index) in services"
      :key="service.kind"
      class="sv-section"
    >
      <div
        v-if="index"
        class="sv-section-divider"
      />
      <div class="sv-section-heading">
        <div>
          <h3>{{ service.title }}</h3>
          <p>{{ service.description }}</p>
        </div>
        <span :class="['sv-status', `is-${providerStatus(service.kind).tone}`]">
          <span class="sv-status-dot" />
          {{ providerStatus(service.kind).label }}
        </span>
      </div>

      <div class="sv-form-stack">
        <settings-form-row label="服务商">
          <n-select
            v-model:value="settings.draft.providers[service.kind].provider"
            :options="providerOptions(service.kind)"
            :loading="settings.providerDetailLoading[service.kind]"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="API Key"
          :hint="
            settings.draftProviderDetails[service.kind].apiKeySet
              ? '留空将继续使用当前服务商已保存的密钥'
              : '密钥只会在保存配置时提交'
          "
        >
          <n-input
            v-model:value="settings.draft.providers[service.kind].apiKey"
            type="password"
            show-password-on="click"
            :placeholder="
              settings.draftProviderDetails[service.kind].apiKeySet
                ? '如需更换，请输入新的 API Key'
                : '输入 API Key'
            "
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          v-if="settings.draftProviderDetails[service.kind].model"
          label="当前模型"
        >
          <div class="sv-readonly-value">
            {{ settings.draftProviderDetails[service.kind].model }}
          </div>
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { NInput, NSelect, useMessage } from 'naive-ui'
import { useLogStore } from '../../stores/log'
import {
  useSettingsStore,
  type ProviderKind,
} from '../../stores/settings'
import type { LlmProviderOption } from '../../models/types'
import SettingsFormRow from './SettingsFormRow.vue'

interface ServiceDescriptor {
  kind: ProviderKind
  title: string
  description: string
}

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const services: ServiceDescriptor[] = [
  {
    kind: 'ocr',
    title: '乐谱 OCR',
    description: '将图片或 PDF 乐谱识别为 MusicXML。',
  },
  {
    kind: 'ai',
    title: 'AI 视觉转写',
    description: '从乐谱图像生成结构化转写结果。',
  },
  {
    kind: 'assistant',
    title: '工作台助手',
    description: '用于工作台中的辅助编辑与问答。',
  },
]

watch(
  () => settings.draft.providers.ocr.provider,
  () => refreshProviderDetails('ocr'),
)
watch(
  () => settings.draft.providers.ai.provider,
  () => refreshProviderDetails('ai'),
)
watch(
  () => settings.draft.providers.assistant.provider,
  () => refreshProviderDetails('assistant'),
)

function providerOptions(kind: ProviderKind): { label: string; value: string }[] {
  return providerSource(kind).map((option) => ({
    label: option.label,
    value: option.id,
  }))
}

function providerSource(kind: ProviderKind): LlmProviderOption[] {
  if (kind === 'ocr') return settings.ocrProviderOptions
  if (kind === 'ai') return settings.aiProviderOptions
  return settings.assistantProviderOptions
}

function providerStatus(kind: ProviderKind): {
  label: string
  tone: 'saved' | 'pending' | 'empty' | 'loading' | 'error'
} {
  if (settings.draft.providers[kind].apiKey.trim()) {
    return { label: '待保存', tone: 'pending' }
  }
  if (settings.providerDetailLoading[kind]) {
    return { label: '正在检查', tone: 'loading' }
  }
  if (settings.providerDetailError[kind]) {
    return { label: '状态未知', tone: 'error' }
  }
  if (settings.draftProviderDetails[kind].apiKeySet) {
    return { label: '已保存', tone: 'saved' }
  }
  return { label: '未配置', tone: 'empty' }
}

function refreshProviderDetails(kind: ProviderKind): void {
  if (!settings.draftReady) return
  void settings.loadDraftProviderDetails(kind).catch((error: unknown) => {
    const text = error instanceof Error ? error.message : String(error)
    log.addError(`加载 Provider 配置失败：${text}`)
    message.error(text)
  })
}
</script>
