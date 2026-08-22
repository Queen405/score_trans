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
  </div>
</template>

<script setup lang="ts">
import { NRadioButton, NRadioGroup, NSwitch } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
</script>
