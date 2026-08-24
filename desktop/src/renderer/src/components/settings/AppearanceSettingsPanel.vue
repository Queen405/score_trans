<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <div>
          <h3>主题外观</h3>
          <p>选择应用界面的明暗模式。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="主题模式"
          hint="主题将在应用或保存设置后切换"
        >
          <n-radio-group
            v-model:value="settings.draft.themeMode"
            class="sv-theme-options"
            size="small"
          >
            <n-radio-button value="system">
              跟随系统
            </n-radio-button>
            <n-radio-button value="light">
              浅色
            </n-radio-button>
            <n-radio-button value="dark">
              深色
            </n-radio-button>
          </n-radio-group>
        </settings-form-row>
      </div>
    </section>

    <div class="sv-section-divider" />

    <section class="sv-section">
      <div class="sv-section-heading">
        <div>
          <h3>预览叠加</h3>
          <p>控制打开预览时识别结果的默认叠加显示。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="识别音符叠加"
          hint="打开原始五线谱图片时默认叠加显示识别到的音符"
        >
          <n-switch
            v-model:value="settings.draft.showRecognitionOverlay"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="简谱 OCR 叠加"
          hint="打开简谱渲染预览时默认叠加显示 OCR 文字"
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
        <div>
          <h3>简谱版式</h3>
          <p>调整 A4 简谱的整体大小与排版密度。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row label="整体大小">
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

        <settings-form-row label="行间距">
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

        <settings-form-row label="短音符间距">
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
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NInputNumber, NRadioButton, NRadioGroup, NSlider, NSwitch } from 'naive-ui'
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
