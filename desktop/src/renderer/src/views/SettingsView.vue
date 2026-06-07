<template>
  <div class="settings-view">
    <h2>设置</h2>
    <p class="subtitle">调整识别引擎、导出路径、OCR 与 AI 服务参数</p>

    <div class="sv-section">
      <div class="sv-section-title">外部工具</div>
      <div class="sv-grid">
        <label>Audiveris 路径</label>
        <n-input v-model:value="settings.audiverisPath" placeholder="audiveris 或 gradlew.bat 路径" size="small">
          <template #prefix><n-icon size="14"><TerminalOutline /></n-icon></template>
        </n-input>

        <label>JDK / JAVA_HOME</label>
        <n-input v-model:value="settings.javaHome" placeholder="JDK 25 路径" size="small">
          <template #prefix><n-icon size="14"><CodeOutline /></n-icon></template>
        </n-input>
      </div>
    </div>

    <div class="sv-section">
      <div class="sv-section-title">转换设置</div>
      <div class="sv-grid">
        <label>简谱调</label>
        <n-input v-model:value="settings.targetKey" placeholder="C" size="small" style="width: 80px" />

        <label>默认导出路径</label>
        <n-input v-model:value="settings.outputDir" placeholder="留空则每次手动选择" size="small">
          <template #suffix>
            <n-button size="tiny" quaternary @click="selectOutputDir">浏览</n-button>
          </template>
        </n-input>
      </div>
    </div>

    <div class="sv-section">
      <div class="sv-section-title">识别预处理</div>
      <div class="sv-grid">
        <label>启用</label>
        <n-switch v-model:value="settings.omrPreprocess" size="small" />

        <label>目标长边</label>
        <n-input-number v-model:value="settings.omrPreprocessLongEdge" :min="0" :step="200" size="small" style="width: 140px" />

        <label>黑白化</label>
        <n-switch v-model:value="settings.omrPreprocessBinarize" size="small" />
      </div>
    </div>

    <div class="sv-section">
      <div class="sv-section-title">OCR 设置</div>
      <div class="sv-grid">
        <label>API Key</label>
        <n-input v-model:value="settings.ocrApiKey" type="password" show-password-on="click" :placeholder="settings.ocrApiKeySet ? '已保存（留空不更新）' : 'API Key'" size="small">
          <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
        </n-input>

        <label>Base URL</label>
        <n-input v-model:value="settings.ocrBaseUrl" placeholder="https://api.siliconflow.cn/v1" size="small">
          <template #prefix><n-icon size="14"><GlobeOutline /></n-icon></template>
        </n-input>

        <label>模型</label>
        <n-input v-model:value="settings.ocrModel" placeholder="deepseek-ai/DeepSeek-OCR" size="small">
          <template #prefix><n-icon size="14"><HardwareChipOutline /></n-icon></template>
        </n-input>
      </div>
    </div>

    <div class="sv-section">
      <div class="sv-section-title">AI 视觉转写</div>
      <div class="sv-grid">
        <label>API Key</label>
        <n-input v-model:value="settings.aiApiKey" type="password" show-password-on="click" :placeholder="settings.aiApiKeySet ? '已保存（留空不更新）' : 'API Key'" size="small">
          <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
        </n-input>

        <label>Base URL</label>
        <n-input v-model:value="settings.aiBaseUrl" placeholder="https://api.siliconflow.cn/v1" size="small">
          <template #prefix><n-icon size="14"><GlobeOutline /></n-icon></template>
        </n-input>

        <label>视觉模型</label>
        <n-input v-model:value="settings.aiModel" placeholder="Qwen/Qwen3-VL-8B-Instruct" size="small">
          <template #prefix><n-icon size="14"><HardwareChipOutline /></n-icon></template>
        </n-input>
      </div>
    </div>

    <div class="sv-section">
      <div class="sv-section-title">工作台 AI 助手</div>
      <div class="sv-grid">
        <label>百炼 Key</label>
        <n-input v-model:value="settings.assistantApiKey" type="password" show-password-on="click" :placeholder="settings.assistantApiKeySet ? '已保存（留空不更新）' : '百炼 API Key'" size="small">
          <template #prefix><n-icon size="14"><KeyOutline /></n-icon></template>
        </n-input>

        <label>Base URL</label>
        <n-input v-model:value="settings.assistantBaseUrl" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" size="small">
          <template #prefix><n-icon size="14"><GlobeOutline /></n-icon></template>
        </n-input>

        <label>模型</label>
        <n-input v-model:value="settings.assistantModel" placeholder="deepseek-v4-flash" size="small">
          <template #prefix><n-icon size="14"><HardwareChipOutline /></n-icon></template>
        </n-input>
      </div>
    </div>

    <div class="sv-footer">
      <n-button type="primary" @click="save">
        <template #icon><n-icon><SaveOutline /></n-icon></template>
        保存配置
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useLogStore } from '../stores/log'
import {
  TerminalOutline,
  KeyOutline,
  GlobeOutline,
  HardwareChipOutline,
  SaveOutline,
  CodeOutline,
} from '@vicons/ionicons5'
import {
  NInput,
  NInputNumber,
  NSwitch,
  NButton,
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

async function selectOutputDir(): Promise<void> {
  const result = await (window as any).api.selectDirectory()
  if (result) settings.outputDir = result
}
</script>

<style scoped>
.settings-view {
  max-width: 640px;
  margin: 0 auto;
}

.settings-view h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 4px 0 20px;
}

.sv-section {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
}

.sv-section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.sv-grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px 12px;
  align-items: center;
}

.sv-grid label {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: right;
}

.sv-footer {
  margin-top: 8px;
}

@media (max-width: 600px) {
  .sv-grid {
    grid-template-columns: 1fr;
  }

  .sv-grid label {
    text-align: left;
  }
}
</style>
