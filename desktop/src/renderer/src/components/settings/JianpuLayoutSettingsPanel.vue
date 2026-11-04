<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layoutPage') }}</h3>
      </div>
      <div class="sv-form-stack">
        <settings-form-row
          :label="t('settings.appearance.measuresPerSystem')"
        >
          <div>
            <n-radio-group
              v-model:value="settings.draft.jianpuMeasuresPerSystem"
              class="sv-theme-options"
              size="small"
            >
              <n-radio-button :value="0">
                {{ t('settings.appearance.measuresAutomatic') }}
              </n-radio-button>
              <n-radio-button
                v-for="count in [3, 4, 5]"
                :key="count"
                :value="count"
              >
                {{ t('settings.appearance.measuresFixed', { count }) }}
              </n-radio-button>
            </n-radio-group>
          </div>
        </settings-form-row>
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
        <settings-form-row :label="t('settings.appearance.marginTop')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuMarginTopMm"
              :min="0"
              :max="50"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuMarginTopMm"
              :min="0"
              :max="50"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.marginBottom')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuMarginBottomMm"
              :min="0"
              :max="50"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuMarginBottomMm"
              :min="0"
              :max="50"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.marginLeft')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuMarginLeftMm"
              :min="0"
              :max="50"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuMarginLeftMm"
              :min="0"
              :max="50"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.marginRight')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuMarginRightMm"
              :min="0"
              :max="50"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuMarginRightMm"
              :min="0"
              :max="50"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.headerGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuHeaderGapMm"
              :min="0"
              :max="30"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuHeaderGapMm"
              :min="0"
              :max="30"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.footerProtection')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuFooterProtectionMm"
              :min="0"
              :max="30"
              :step="0.5"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuFooterProtectionMm"
              :min="0"
              :max="30"
              :step="0.5"
              size="small"
            >
              <template #suffix>
                mm
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
      </div>
    </section>
    <div class="sv-section-divider" />
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layoutTypography') }}</h3>
      </div>
      <div class="sv-form-stack">
        <settings-form-row :label="t('settings.appearance.noteSize')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuNoteSizePercent"
              :min="70"
              :max="140"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuNoteSizePercent"
              :min="70"
              :max="140"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.lyricSize')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuLyricSizePercent"
              :min="60"
              :max="150"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuLyricSizePercent"
              :min="60"
              :max="150"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.titleSize')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuTitleSizePercent"
              :min="60"
              :max="160"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuTitleSizePercent"
              :min="60"
              :max="160"
              :step="1"
              size="small"
            >
              <template #suffix>
                %
              </template>
            </n-input-number>
          </div>
        </settings-form-row>
        <settings-form-row :label="t('settings.appearance.annotationSize')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuAnnotationSizePercent"
              :min="60"
              :max="150"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuAnnotationSizePercent"
              :min="60"
              :max="150"
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
    <div class="sv-section-divider" />
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layoutVoices') }}</h3>
      </div>
      <div class="sv-form-stack">
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
        <settings-form-row :label="t('settings.appearance.partGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuPartGapPercent"
              :min="50"
              :max="200"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuPartGapPercent"
              :min="50"
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
        <settings-form-row :label="t('settings.appearance.voiceGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuVoiceGapPercent"
              :min="50"
              :max="200"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuVoiceGapPercent"
              :min="50"
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
    <div class="sv-section-divider" />
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layoutLyrics') }}</h3>
      </div>
      <div class="sv-form-stack">
        <settings-form-row :label="t('settings.appearance.lyricLineGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuLyricLineGapPercent"
              :min="50"
              :max="200"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuLyricLineGapPercent"
              :min="50"
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
        <settings-form-row :label="t('settings.appearance.lyricNoteGap')">
          <div class="sv-layout-control">
            <n-slider
              v-model:value="settings.draft.jianpuLyricNoteGapPercent"
              :min="50"
              :max="200"
              :step="1"
            />
            <n-input-number
              v-model:value="settings.draft.jianpuLyricNoteGapPercent"
              :min="50"
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
    <div class="sv-section-divider" />
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>{{ t('settings.appearance.layoutRhythm') }}</h3>
      </div>
      <div class="sv-form-stack">
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
        <settings-form-row :label="t('settings.appearance.breakBeamsAtBeat')">
          <n-switch v-model:value="settings.draft.jianpuBreakBeamsAtBeat" />
        </settings-form-row>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NInputNumber, NRadioButton, NRadioGroup, NSlider, NSwitch } from 'naive-ui'
import { t } from '../../i18n'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
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
