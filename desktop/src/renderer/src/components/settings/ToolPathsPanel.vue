<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.tools.title') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.tools.audiveris')"
        >
          <n-input
            v-model:value="settings.draft.audiverisPath"
            :placeholder="t('settings.tools.audiverisPlaceholder')"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.javaHome')"
        >
          <n-input
            v-model:value="settings.draft.javaHome"
            :placeholder="t('settings.tools.javaHomePlaceholder')"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.maxHeap')"
        >
          <n-radio-group
            v-model:value="settings.draft.audiverisMaxHeap"
            class="sv-theme-options"
            size="small"
          >
            <n-radio-button
              v-for="option in heapOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.pixelLimit')"
        >
          <n-input-number
            v-model:value="maxPixelCountNumber"
            :min="0"
            :step="1000000"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.binarizationThreshold')"
        >
          <n-input-number
            v-model:value="settings.draft.audiverisBinarizationThreshold"
            :min="0"
            :max="254"
            :step="1"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.autoUpscale')"
        >
          <n-switch
            v-model:value="settings.draft.audiverisAutoUpscale"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.minImageEdge')"
        >
          <n-input-number
            v-model:value="settings.draft.audiverisMinImageEdge"
            :min="0"
            :max="10000"
            :step="100"
            :disabled="!settings.draft.audiverisAutoUpscale"
            size="small"
          />
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { NInput, NInputNumber, NRadioButton, NRadioGroup, NSwitch } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'
import { t } from '../../i18n'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()

const heapOptions = [
  { label: '1G', value: '1g' },
  { label: '2G', value: '2g' },
  { label: '3G', value: '3g' },
  { label: '4G', value: '4g' },
]

const maxPixelCountNumber = computed({
  get: () => Number(settings.draft.audiverisMaxPixelCount) || 0,
  set: (v: number) => {
    settings.draft.audiverisMaxPixelCount = String(v)
  },
})
</script>
