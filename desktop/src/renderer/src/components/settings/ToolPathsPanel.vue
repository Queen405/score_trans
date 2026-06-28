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
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { NInput } from 'naive-ui'
import { useSettingsStore } from '../../stores/settings'
import SettingsFormRow from './SettingsFormRow.vue'

const settings = useSettingsStore()
</script>
