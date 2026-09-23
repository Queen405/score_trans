<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    class="api-key-missing-modal"
    :title="t('common.apiKeyMissing.title')"
    :bordered="false"
    :mask-closable="false"
    :closable="false"
    @esc="settings.clearApiKeyMissing"
  >
    <p class="api-key-missing-copy">
      {{ message }}
    </p>
    <template #footer>
      <div class="api-key-missing-actions">
        <n-button @click="settings.clearApiKeyMissing">
          {{ t('common.action.cancel') }}
        </n-button>
        <n-button
          type="primary"
          @click="settings.requestOpenSettings"
        >
          {{ t('common.apiKeyMissing.goSettings') }}
        </n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NModal } from 'naive-ui'
import { t } from '../i18n'
import { useSettingsStore } from '../stores/settings'

const settings = useSettingsStore()

const visible = computed<boolean>({
  get: () => settings.apiKeyMissingVisible,
  set: (value) => {
    if (!value) settings.clearApiKeyMissing()
  },
})

const message = computed(() => {
  const kind = settings.apiKeyMissingKind
  if (kind === 'ocr') return t('common.apiKeyMissing.messageOcr')
  if (kind === 'ai') return t('common.apiKeyMissing.messageAi')
  if (kind === 'assistant') return t('common.apiKeyMissing.messageAssistant')
  return t('common.apiKeyMissing.messageDefault')
})
</script>

<style>
.api-key-missing-modal {
  width: 420px;
  max-width: calc(100vw - 32px);
}

.api-key-missing-copy {
  margin: 0;
  line-height: 1.6;
}

.api-key-missing-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
