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
  </div>
</template>

<script setup lang="ts">
import { NRadioButton, NRadioGroup } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
</script>
