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
          :label="t('settings.tools.pdfDpiMode')"
        >
          <div class="sv-auto-number">
            <n-checkbox v-model:checked="pdfDpiAuto">
              {{ t('settings.tools.pdfDpiAuto') }}
            </n-checkbox>
            <n-input-number
              v-model:value="manualPdfUploadDpi"
              :min="72"
              :max="600"
              :step="1"
              :disabled="pdfDpiAuto"
              size="small"
            />
          </div>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.tools.binarizationMode')"
        >
          <div class="sv-auto-number">
            <n-checkbox v-model:checked="binarizationAuto">
              {{ t('settings.tools.binarizationAuto') }}
            </n-checkbox>
            <n-input-number
              v-model:value="manualBinarizationThreshold"
              :min="1"
              :max="254"
              :step="1"
              :disabled="binarizationAuto"
              size="small"
            />
          </div>
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
import { computed, ref, watch } from 'vue'
import { NCheckbox, NInput, NInputNumber, NRadioButton, NRadioGroup, NSwitch } from 'naive-ui'
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

const lastManualPdfUploadDpi = ref(300)
watch(
  () => settings.draft.pdfUploadDpi,
  (value) => {
    if (value > 0) lastManualPdfUploadDpi.value = value
  },
  { immediate: true },
)

const pdfDpiAuto = computed<boolean>({
  get: () => settings.draft.pdfUploadDpi === 0,
  set: (automatic) => {
    settings.draft.pdfUploadDpi = automatic ? 0 : lastManualPdfUploadDpi.value
  },
})
const manualPdfUploadDpi = computed<number>({
  get: () => settings.draft.pdfUploadDpi || lastManualPdfUploadDpi.value,
  set: (value: number | null) => {
    if (value === null || pdfDpiAuto.value) return
    settings.draft.pdfUploadDpi = value
  },
})

const lastManualBinarizationThreshold = ref(210)
watch(
  () => settings.draft.audiverisBinarizationThreshold,
  (value) => {
    if (value > 0) lastManualBinarizationThreshold.value = value
  },
  { immediate: true },
)

const binarizationAuto = computed<boolean>({
  get: () => settings.draft.audiverisBinarizationThreshold === 0,
  set: (automatic) => {
    settings.draft.audiverisBinarizationThreshold = automatic
      ? 0
      : lastManualBinarizationThreshold.value
  },
})
const manualBinarizationThreshold = computed<number>({
  get: () => (
    settings.draft.audiverisBinarizationThreshold
    || lastManualBinarizationThreshold.value
  ),
  set: (value: number | null) => {
    if (value === null || binarizationAuto.value) return
    settings.draft.audiverisBinarizationThreshold = value
  },
})

const maxPixelCountNumber = computed({
  get: () => Number(settings.draft.audiverisMaxPixelCount) || 0,
  set: (v: number) => {
    settings.draft.audiverisMaxPixelCount = String(v)
  },
})
</script>

<style scoped>
.sv-auto-number {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 560px;
}

.sv-auto-number .n-checkbox {
  flex-shrink: 0;
}

.sv-auto-number .n-input-number {
  flex: 1;
}
</style>
