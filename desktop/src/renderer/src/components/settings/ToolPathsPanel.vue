<template>
  <div class="sv-panel">
    <section class="sv-section">
      <div class="sv-section-heading">
        <div>
          <h3>识别工具</h3>
          <p>配置乐谱识别所需的本地工具环境。</p>
        </div>
      </div>

      <div class="sv-form-stack">
        <settings-form-row
          label="Audiveris"
          description="识别引擎"
          hint="可填写 Audiveris 可执行文件或项目中的 gradlew.bat 路径"
        >
          <n-input
            v-model:value="settings.draft.audiverisPath"
            placeholder="audiveris 或 gradlew.bat 路径"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="Java 环境"
          description="JAVA_HOME"
          hint="Audiveris 需要 JDK 25，保存后将在下次识别时使用"
        >
          <n-input
            v-model:value="settings.draft.javaHome"
            placeholder="JDK 25 目录"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="最大堆内存"
          description="Audiveris JVM 内存上限"
          hint="启动崩溃时调小此值；21MP 曲谱约需 1-2g"
        >
          <n-select
            v-model:value="settings.draft.audiverisMaxHeap"
            :options="heapOptions"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="像素上限"
          description="图片宽×高 的最大像素数"
          hint="超过此值 Audiveris 拒绝处理；0=不限制"
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
          description="识别前把图片长边放大到指定像素"
          hint="提升低分辨率谱面识别率；关闭后低分辨率重试也会一并关闭"
        >
          <n-switch
            v-model:value="settings.draft.audiverisAutoUpscale"
            size="small"
          />
        </settings-form-row>

        <settings-form-row
          label="最小长边像素"
          description="放大目标值"
          hint="图片长边低于此值时放大到该像素；数值越大放大越多，0 表示不放大"
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
