<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <h3>识别工具</h3>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="Audiveris"
        >
          <n-input
            v-model:value="settings.draft.audiverisPath"
            placeholder="audiveris 或 gradlew 脚本路径"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="Java 环境"
        >
          <n-input
            v-model:value="settings.draft.javaHome"
            placeholder="JDK 25 目录"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="最大堆内存"
        >
          <n-select
            v-model:value="settings.draft.audiverisMaxHeap"
            :options="heapOptions"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="像素上限"
        >
          <n-input-number
            v-model:value="maxPixelCountNumber"
            :min="0"
            :step="1000000"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="自动放大图片"
        >
          <n-switch
            v-model:value="settings.draft.audiverisAutoUpscale"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="最小长边像素"
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
import { NInput, NInputNumber, NSelect, NSwitch } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'
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
