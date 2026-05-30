<template>
  <div class="settings-view">
    <n-card title="⚙️ 外部工具配置" :bordered="false" class="settings-card">
      <n-form label-placement="left" label-width="140" size="large">
        <n-form-item label="Audiveris 路径">
          <n-input
            v-model:value="settings.audiverisPath"
            placeholder="audiveris 或 gradlew.bat 路径"
          >
            <template #prefix><n-icon><TerminalOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item label="MuseScore 路径">
          <n-input
            v-model:value="settings.musescorePath"
            placeholder="musescore 或 MuseScore4.exe 路径"
          >
            <template #prefix><n-icon><MusicalNotesOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item label="JDK / JAVA_HOME">
          <n-input v-model:value="settings.javaHome" placeholder="JDK 25 路径">
            <template #prefix><n-icon><CodeOutline /></n-icon></template>
          </n-input>
        </n-form-item>

        <n-divider>转换设置</n-divider>

        <n-form-item label="简谱调">
          <n-input
            v-model:value="settings.targetKey"
            placeholder="C"
            style="width: 100px"
          />
        </n-form-item>
        <n-form-item label="起始小节号">
          <n-input-number
            v-model:value="settings.startMeasureNumber"
            placeholder="留空使用原小节号"
            clearable
            style="width: 180px"
          />
        </n-form-item>
        <n-form-item label="默认导出路径">
          <n-input-group>
            <n-input
              v-model:value="settings.outputDir"
              placeholder="留空则每次手动选择"
            />
            <n-button @click="selectOutputDir" secondary>浏览</n-button>
          </n-input-group>
        </n-form-item>

        <n-divider>OCR 设置</n-divider>

        <n-form-item label="OCR API Key">
          <n-input
            v-model:value="settings.ocrApiKey"
            type="password"
            show-password-on="click"
            placeholder="SCORE_TRANS_OCR_API_KEY"
          >
            <template #prefix><n-icon><KeyOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item label="OCR Base URL">
          <n-input
            v-model:value="settings.ocrBaseUrl"
            placeholder="https://api.siliconflow.cn/v1"
          >
            <template #prefix><n-icon><GlobeOutline /></n-icon></template>
          </n-input>
        </n-form-item>
        <n-form-item label="OCR 模型">
          <n-input
            v-model:value="settings.ocrModel"
            placeholder="deepseek-ai/DeepSeek-OCR"
          >
            <template #prefix><n-icon><HardwareChipOutline /></n-icon></template>
          </n-input>
        </n-form-item>

        <n-form-item>
          <n-space>
            <n-button type="primary" @click="save" size="large">
              <template #icon><n-icon><SaveOutline /></n-icon></template>
              保存配置
            </n-button>
          </n-space>
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import {
  TerminalOutline,
  MusicalNotesOutline,
  KeyOutline,
  GlobeOutline,
  HardwareChipOutline,
  SaveOutline,
  CodeOutline,
} from '@vicons/ionicons5'
import {
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputGroup,
  NInputNumber,
  NButton,
  NSpace,
  NDivider,
  NIcon,
  useMessage,
} from 'naive-ui'

const settings = useSettingsStore()
const log = useLogStore()
const message = useMessage()

onMounted(() => settings.load())

async function save(): Promise<void> {
  try {
    await settings.save()
    log.addLog('配置已保存')
    message.success('配置已保存')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    log.addError(`保存失败：${msg}`)
    message.error(msg)
  }
}

function selectOutputDir(): void {
  const path = prompt('请输入导出路径：', settings.outputDir)
  if (path !== null) {
    settings.outputDir = path
  }
}
</script>

<style scoped>
.settings-view {
  max-width: 800px;
}

.settings-card {
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
</style>
