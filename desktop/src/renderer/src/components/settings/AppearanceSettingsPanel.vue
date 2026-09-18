<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('common.language.label') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('common.language.interface')"
        >
          <n-radio-group
            :value="locale"
            class="sv-theme-options"
            size="small"
            @update:value="onLocaleChange"
          >
            <n-radio-button
              v-for="option in localeOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.theme') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.appearance.themeMode')"
        >
          <n-radio-group
            v-model:value="settings.draft.themeMode"
            class="sv-theme-options"
            size="small"
          >
            <n-radio-button value="system">
              {{ t('settings.appearance.themeSystem') }}
            </n-radio-button>
            <n-radio-button value="light">
              {{ t('settings.appearance.themeLight') }}
            </n-radio-button>
            <n-radio-button value="dark">
              {{ t('settings.appearance.themeDark') }}
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.overlay') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.appearance.recognitionOverlay')"
        >
          <n-switch
            v-model:value="settings.draft.showRecognitionOverlay"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          :label="t('settings.appearance.ocrOverlay')"
        >
          <n-switch
            v-model:value="settings.draft.showOcrOverlay"
            size="small"
          />
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layout') }}</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row :label="t('settings.appearance.contentScale')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuContentScalePercent"
              :min="65"
              :max="100"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuContentScalePercent"
              :min="65"
              :max="100"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>

        <settings-form-row :label="t('settings.appearance.systemGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuSystemGapPercent"
              :min="20"
              :max="180"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuSystemGapPercent"
              :min="20"
              :max="180"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.appearance.shortNoteGap')"
        >
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuShortNoteGapPercent"
              :min="20"
              :max="180"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuShortNoteGapPercent"
              :min="20"
              :max="180"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>

        <settings-form-row
          :label="t('settings.appearance.beatGap')"
        >
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuBeatGapPercent"
              :min="0"
              :max="200"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuBeatGapPercent"
              :min="0"
              :max="200"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NInputNumber, NRadioButton, NRadioGroup, NSlider, NSwitch } from 'naive-ui'
import {
  LOCALE_OPTIONS,
  isLocaleCode,
  locale,
  setLocale,
  t,
} from '../../i18n'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
const localeOptions = LOCALE_OPTIONS

function onLocaleChange(value: string): void {
  if (isLocaleCode(value)) {
    setLocale(value)
  }
}
</script>

<style scoped>
.sv-layout-control {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 108px;
  align-items: center;
  gap: 16px;
  max-width: 560px;
}

@media (max-width: 720px) {
  .sv-layout-control {
    grid-template-columns: minmax(0, 1fr) 96px;
  }
}
</style>
