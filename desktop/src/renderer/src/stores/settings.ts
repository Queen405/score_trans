import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi } from '../api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const audiverisPath = ref('')
  const musescorePath = ref('')
  const javaHome = ref('')
  const targetKey = ref('C')
  const startMeasureNumber = ref<number | null>(null)
  const outputDir = ref('')
  const ocrApiKey = ref('')
  const ocrApiKeySet = ref(false)
  const ocrBaseUrl = ref('https://api.siliconflow.cn/v1')
  const ocrModel = ref('deepseek-ai/DeepSeek-OCR')
  const loaded = ref(false)

  async function load(): Promise<void> {
    try {
      const data = await settingsApi.get()
      audiverisPath.value = data.audiveris_path
      musescorePath.value = data.musescore_path
      javaHome.value = data.java_home
      outputDir.value = data.output_dir ?? ''
      ocrApiKey.value = data.ocr_api_key ?? ''
      ocrApiKeySet.value = data.ocr_api_key_set ?? false
      ocrBaseUrl.value = data.ocr_base_url ?? 'https://api.siliconflow.cn/v1'
      ocrModel.value = data.ocr_model ?? 'deepseek-ai/DeepSeek-OCR'
      loaded.value = true
    } catch (e) {
      console.error('Failed to load settings:', e)
    }
  }

  async function save(): Promise<void> {
    await settingsApi.update({
      audiveris_path: audiverisPath.value,
      musescore_path: musescorePath.value,
      java_home: javaHome.value,
      output_dir: outputDir.value,
      ocr_api_key: ocrApiKey.value || undefined,
      ocr_base_url: ocrBaseUrl.value,
      ocr_model: ocrModel.value,
    })
  }

  return {
    audiverisPath,
    musescorePath,
    javaHome,
    targetKey,
    startMeasureNumber,
    outputDir,
    ocrApiKey,
    ocrApiKeySet,
    ocrBaseUrl,
    ocrModel,
    loaded,
    load,
    save,
  }
})
