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
        <h3>{{ service.title }}</h3>
        <span :class="['sv-status', `is-${providerStatus(service.kind).tone}`]">
          <span class="sv-status-dot" />
          {{ providerStatus(service.kind).label }}
        </span>
      </div>

      <div class="sv-form-stack">
        <settings-form-row :label="t('settings.service.provider')">
          <n-select
            v-model:value="settings.draft.providers[service.kind].provider"
            :options="providerOptions(service.kind)"
            :loading="settings.providerDetailLoading[service.kind]"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.service.apiKey')"
        >
          <n-input
            v-model:value="settings.draft.providers[service.kind].apiKey"
            type="password"
            show-password-on="click"
            :placeholder="
              settings.draftProviderDetails[service.kind].apiKeySet
                ? t('settings.service.apiKeyReplacePlaceholder')
                : t('settings.service.apiKeyPlaceholder')
            "
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          v-if="settings.draftProviderDetails[service.kind].model"
          :label="t('settings.service.currentModel')"
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
import { computed, watch } from 'vue'
import { NInput, NSelect, useMessage } from 'naive-ui'
import { useLogStore } from '../../stores/log'
import { t } from '../../i18n'
import {
  useSettingsStore,
  type ProviderKind,
} from '../../stores/settings'
import type { LlmProviderOption } from '../../models/types'
import SettingsFormRow from './SettingsFormRow.vue'

interface ServiceDescriptor {
  kind: ProviderKind
  title: string
}

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

const services = computed<ServiceDescriptor[]>(() => [
  {
    kind: 'ocr',
    title: t('settings.service.ocr'),
  },
  {
    kind: 'ai',
    title: t('settings.service.ai'),
  },
  {
    kind: 'assistant',
    title: t('settings.service.assistant'),
  },
])

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
    return { label: t('settings.service.statusPending'), tone: 'pending' }
  }
  if (settings.providerDetailLoading[kind]) {
    return { label: t('settings.service.statusLoading'), tone: 'loading' }
  }
  if (settings.providerDetailError[kind]) {
    return { label: t('settings.service.statusError'), tone: 'error' }
  }
  if (settings.draftProviderDetails[kind].apiKeySet) {
    return { label: t('settings.service.statusSaved'), tone: 'saved' }
  }
  return { label: t('settings.service.statusEmpty'), tone: 'empty' }
}

function refreshProviderDetails(kind: ProviderKind): void {
  if (!settings.draftReady) return
  void settings.loadDraftProviderDetails(kind).catch((error: unknown) => {
    const text = error instanceof Error ? error.message : String(error)
    log.addError(t('settings.service.loadFailed', { text }))
    message.error(text)
  })
}
</script>
